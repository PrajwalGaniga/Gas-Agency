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
    // Determine API Base URL intelligently
    await ApiService.initBaseUrl();

    // Check for existing session using SharedPreferences
    authData = await ApiService().checkAutoLogin();
  } catch (e) {
    debugPrint("Session check failed: $e");
  }

  runApp(MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'GasFlow Driver',
    themeMode: ThemeMode.dark,
    theme: ThemeData(
      brightness: Brightness.dark,
      useMaterial3: true,
      scaffoldBackgroundColor: const Color(0xFF0F172A), // Slate 900
      primaryColor: const Color(0xFF4F46E5), // Indigo 600
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF020617), // Slate 950
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: Colors.white, 
          fontSize: 22, 
          fontWeight: FontWeight.bold,
          fontFamily: 'Space Grotesk'
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF4F46E5), // Indigo 600
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 60), // GLOVE-FRIENDLY HUGE BUTTONS
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(
            fontSize: 18, 
            fontWeight: FontWeight.bold,
            letterSpacing: 1.2
          ),
          elevation: 4,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFF1E293B), // Slate 800
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: Color(0xFF6366F1), width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
        labelStyle: const TextStyle(color: Color(0xFF94A3B8)), // Slate 400
      ),
      cardTheme: CardThemeData(
        color: const Color(0xFF1E293B), // Slate 800
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        elevation: 0,
        margin: const EdgeInsets.symmetric(vertical: 8),
      ),
    ),
    // If session exists, skip login and go straight to Dashboard
    home: authData == null 
        ? const LoginScreen() 
        : HomeScreen(driverData: authData['driver'], token: authData['token']),
  ));
}