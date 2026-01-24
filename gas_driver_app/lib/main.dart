import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'services/api_service.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';

void main() async {
  // 🚀 CRITICAL: Ensures Flutter engine is ready for background tasks and Hive
  WidgetsFlutterBinding.ensureInitialized();

  // 📦 INITIALIZE HIVE: Sets up local database storage on the phone
  try {
    await Hive.initFlutter();
    
    // 🚀 CRITICAL: You MUST 'await' these so they are ready before the UI builds
    await Hive.openBox(ApiService.orderBoxName);      // Box: "cached_orders"
    await Hive.openBox(ApiService.syncQueueBoxName); // Box: "sync_queue"
    
    debugPrint("Hive boxes opened successfully.");
  } catch (e) {
    debugPrint("Hive failed to open: $e");
  }

  Map<String, dynamic>? authData;
  try {
    // Check for existing session using SharedPreferences
    authData = await ApiService().checkAutoLogin();
  } catch (e) {
    debugPrint("Session check failed: $e");
  }

  runApp(MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'GasFlow Driver',
    theme: ThemeData(
      brightness: Brightness.dark, // Matching your deep dark theme
      useMaterial3: true,
      colorSchemeSeed: const Color(0xFF2979FF), // High Vis Blue
    ),
    // If session exists, skip login and go straight to Dashboard
    home: authData == null 
        ? const LoginScreen() 
        : HomeScreen(driverData: authData['driver'], token: authData['token']),
  ));
}