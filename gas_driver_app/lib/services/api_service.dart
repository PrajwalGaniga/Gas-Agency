import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static const String baseUrl = "https://gas-agency-backend-go6b.onrender.com"; // Emulator Localhost

  // Persists login data to local storage
  Future<void> saveSession(String token, Map driver) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('token', token);
    await prefs.setString('driverData', jsonEncode(driver));
  }

  // Checks for existing session on app launch
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
  }

  // Driver Login via JSON
  Future<Map<String, dynamic>> login(String phone, String password) async {
    final res = await http.post(Uri.parse('$baseUrl/driver/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'phone_number': phone, 'password': password}));
    return jsonDecode(res.body);
  }

  // Fetches ALL assigned orders for the checklist
  Future<Map<String, dynamic>> getOrders(String cities, String token, double lat, double lng, String date) async {
    final res = await http.get(
      Uri.parse('$baseUrl/driver/orders?cities=$cities&lat=$lat&lng=$lng&date=$date'),
      headers: {'Authorization': 'Bearer $token'},
    );
    return jsonDecode(res.body);
  }

  // 🚀 FIXED: The missing acceptOrder function
  // Moves order from PENDING (Orange) to IN_PROGRESS (Blue)
  Future<Map<String, dynamic>> acceptOrder(String token, String orderId) async {
    try {
      final res = await http.post(
        Uri.parse('$baseUrl/driver/accept-order'),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
        body: jsonEncode({'order_id': orderId}),
      );
      return jsonDecode(res.body);
    } catch (e) {
      return {'success': false, 'message': 'Connection error: $e'};
    }
  }

  // Marks delivery complete and saves verified GPS
  Future<Map<String, dynamic>> completeOrder(String token, String orderId, double lat, double lng) async {
    final res = await http.post(
      Uri.parse('$baseUrl/driver/complete-order'),
      headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
      body: jsonEncode({'order_id': orderId, 'lat': lat, 'lng': lng}),
    );
    return jsonDecode(res.body);
  }

  // Sends Field Change Requests to Admin
  Future<Map<String, dynamic>> submitChangeRequest(String token, Map data) async {
    final res = await http.post(
      Uri.parse('$baseUrl/driver/change-request'),
      headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
      body: jsonEncode(data),
    );
    return jsonDecode(res.body);
  }

  // 🛰️ GPS Heartbeat: Required for 'Work Hours' calculation in Admin Audit
  Future<void> sendLocationPing(String token, double lat, double lng) async {
    try {
      await http.post(
        Uri.parse('$baseUrl/driver/location'),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
        body: jsonEncode({'lat': lat, 'lng': lng}),
      );
    } catch (e) {
      print("Location Ping Failed: $e");
    }
  }
}