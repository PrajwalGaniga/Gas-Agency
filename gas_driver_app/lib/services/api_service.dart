import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:hive_flutter/hive_flutter.dart';

class ApiService {
  static String baseUrl = "https://gas-agency-backend-go6b.onrender.com";
  static const String _ngrokUrl = "https://dawdlingly-pseudoinsane-pa.ngrok-free.dev";
  static const String _renderUrl = "https://gas-agency-backend-go6b.onrender.com";
  static const String _emulatorUrl = "http://10.0.2.2:8000"; // 📱 Standard Android Emulator Host
  static bool _initialized = false;

  // --- DYNAMIC ROUTING ENGINE ---
  static Future<void> initBaseUrl() async {
    if (_initialized) return;
    try {
      print("🔍 Checking local server (Emulator)...");
      final res = await http.get(Uri.parse('$_emulatorUrl/docs')).timeout(const Duration(seconds: 1));
      if (res.statusCode == 200) {
        baseUrl = _emulatorUrl;
        print("📱 Connected to EMULATOR local server: $baseUrl");
        _initialized = true;
        return;
      }
    } catch (_) {}

    try {
      print("🔍 Checking Ngrok server...");
      final res = await http.get(Uri.parse('$_ngrokUrl/docs')).timeout(const Duration(seconds: 2));
      baseUrl = _ngrokUrl;
      print("🔌 Connected to NGROK local server: $baseUrl");
    } catch (e) {
      baseUrl = _renderUrl;
      print("☁️ Ngrok not reachable. Using RENDER cloud server: $baseUrl");
    }
    _initialized = true;
  }

  // Hive Box Names
  static const String orderBoxName = "cached_orders";
  static const String syncQueueBoxName = "sync_queue";
  static const String settingsBoxName = "settings"; // 📦 Added: For shift status & app settings

  // --- SESSION MANAGEMENT ---
  Future<void> saveSession(String token, Map driver) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('token', token);
    await prefs.setString('driverData', jsonEncode(driver));
  }

  Future<Map<String, dynamic>?> checkAutoLogin() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    final data = prefs.getString('driverData');
    if (token != null && data != null) {
      return {'token': token, 'driver': jsonDecode(data)};
    }
    return null;
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    await Hive.box(orderBoxName).clear();
    await Hive.box(syncQueueBoxName).clear();
  }

  // --- AUTHENTICATION ---
  Future<Map<String, dynamic>> login(String phone, String password) async {
    try {
      print("🚀 Attempting Login at: $baseUrl/driver/login");
      final res = await http.post(Uri.parse('$baseUrl/driver/login'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'phone_number': phone, 'password': password}));
      
      final data = jsonDecode(res.body);
      if (res.statusCode == 200) {
        return data;
      } else {
        // Handle FastAPI detail errors
        return {
          'success': false, 
          'message': data['detail'] ?? 'Login failed (${res.statusCode})'
        };
      }
    } catch (e) {
      return {'success': false, 'message': 'Network error: $baseUrl might be offline.'};
    }
  }

  // --- OFFLINE-READY ORDER FETCHING ---
  Future<Map<String, dynamic>> getOrders(String cities, String token, double lat, double lng, String date) async {
    var box = Hive.box(orderBoxName);

    try {
      final res = await http.get(
        Uri.parse('$baseUrl/driver/orders?cities=$cities&lat=$lat&lng=$lng&date=$date'),
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 10));

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        // 💾 Cache successful response for offline use
        await box.put('last_orders', res.body);
        return data;
      }
    } catch (e) {
      print("Offline Mode: Loading cached orders.");
    }

    // 🏮 Fallback: Load from Cache
    String? cachedData = box.get('last_orders');
    if (cachedData != null) {
      return jsonDecode(cachedData);
    }

    return {'orders': [], 'message': 'No internet and no cached data.'};
  }

  // --- ACTION QUEUEING (OFFLINE SYNC) ---
  Future<Map<String, dynamic>> completeOrder(String token, String orderId, double lat, double lng, int emptiesCollected, String paymentMode, double amountCollected) async {
    final payload = {
      'order_id': orderId, 
      'lat': lat, 
      'lng': lng,
      'empties_collected': emptiesCollected,
      'payment_mode': paymentMode,
      'amount_collected': amountCollected
    };

    try {
      // 1. Try Live Update
      final res = await http.post(
        Uri.parse('$baseUrl/driver/complete-order'),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
        body: jsonEncode(payload),
      ).timeout(const Duration(seconds: 8));

      return jsonDecode(res.body);
    } catch (e) {
      // 2. 📴 NETWORK FAILED: Queue the action locally
      var syncBox = Hive.box(syncQueueBoxName);
      List currentQueue = syncBox.get('pending_completions', defaultValue: []);
      
      // Prevent duplicate queueing
      if (!currentQueue.any((item) => item['order_id'] == orderId)) {
        currentQueue.add(payload);
        await syncBox.put('pending_completions', currentQueue);
        
        // 💾 OFFLINE STOCK UPDATE: Update the cached shift status so UI stays accurate
        var box = Hive.box(ApiService.settingsBoxName);
        String? cachedShift = box.get('last_shift_status');
        if (cachedShift != null) {
          Map<String, dynamic> shift = jsonDecode(cachedShift);
          if (shift['active'] == true) {
            shift['inventory']['full_cylinders'] = (shift['inventory']['full_cylinders'] as int) - 1;
            shift['inventory']['empty_cylinders'] = (shift['inventory']['empty_cylinders'] as int) + emptiesCollected;
            if (paymentMode == 'CASH') {
              // We don't know the price here easily without searching orders, 
              // but we can at least update cylinder counts which is most critical.
            }
            await box.put('last_shift_status', jsonEncode(shift));
          }
        }
      }

      return {
        'success': true, 
        'offline': true,
        'message': 'Saved locally. Will sync when network returns.'
      };
    }
  }

  // --- BACKGROUND SYNC ENGINE ---
  Future<void> processSyncQueue(String token) async {
    var syncBox = Hive.box(syncQueueBoxName);
    List pending = syncBox.get('pending_completions', defaultValue: []);

    if (pending.isEmpty) return;

    List remaining = List.from(pending);
    for (var action in pending) {
      try {
        final res = await http.post(
          Uri.parse('$baseUrl/driver/complete-order'),
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
          body: jsonEncode(action),
        );

        if (res.statusCode == 200) {
          remaining.remove(action);
          print("Successfully synced order: ${action['order_id']}");
        }
      } catch (e) {
        print("Sync failed for ${action['order_id']}, will retry later.");
        break; // Stop loop if network is still down
      }
    }
    await syncBox.put('pending_completions', remaining);
  }

  // --- OTHER API CALLS ---
  Future<Map<String, dynamic>> acceptOrder(String token, String orderId) async {
    try {
      final res = await http.post(
        Uri.parse('$baseUrl/driver/accept-order'),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
        body: jsonEncode({'order_id': orderId}),
      );
      return jsonDecode(res.body);
    } catch (e) {
      return {'success': false, 'message': 'Network required to accept new orders.'};
    }
  }

  Future<Map<String, dynamic>> submitChangeRequest(String token, Map data) async {
    try {
      final res = await http.post(
        Uri.parse('$baseUrl/driver/change-request'),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
        body: jsonEncode(data),
      );
      return jsonDecode(res.body);
    } catch (e) {
      return {'success': false, 'message': 'Network error.'};
    }
  }

  Future<void> sendLocationPing(String token, double lat, double lng) async {
    try {
      await http.post(
        Uri.parse('$baseUrl/driver/location'),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
        body: jsonEncode({'lat': lat, 'lng': lng}),
      ).timeout(const Duration(seconds: 5));
    } catch (_) {}
  }

  Future<Map<String, dynamic>> getShiftStatus(String token) async {
    var box = Hive.box(ApiService.settingsBoxName);
    try {
      final res = await http.get(
        Uri.parse('$baseUrl/driver/shift/status'),
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 5));
      
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        await box.put('last_shift_status', res.body);
        return data;
      }
    } catch (e) {
      print("Shift Status Offline: Loading cache.");
    }
    
    String? cached = box.get('last_shift_status');
    if (cached != null) return jsonDecode(cached);
    return {'active': false, 'message': 'Network error'};
  }

  Future<int> getSyncQueueCount() async {
    var syncBox = Hive.box(ApiService.syncQueueBoxName);
    List pending = syncBox.get('pending_completions', defaultValue: []);
    return pending.length;
  }
}
