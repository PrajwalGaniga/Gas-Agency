import 'package:flutter/material.dart';
import 'services/api_service.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';

void main() async {
  // 🚀 CRITICAL: Fixes the isolate crash by ensuring engine readiness
  WidgetsFlutterBinding.ensureInitialized();
  
  Map<String, dynamic>? authData;
  try {
    // Purpose: One-time login check using SharedPreferences
    authData = await ApiService().checkAutoLogin();
  } catch (e) {
    debugPrint("Session check failed: $e");
  }

  runApp(MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'GasFlow Driver',
    theme: ThemeData(
      useMaterial3: true,
      colorSchemeSeed: Colors.indigo,
    ),
    // If session exists, skip login and go straight to Dashboard
    home: authData == null 
        ? const LoginScreen() 
        : HomeScreen(driverData: authData['driver'], token: authData['token']),
  ));
}