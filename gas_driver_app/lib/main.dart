import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'services/api_service.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Set status bar to light (dark icons on white background)
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
    statusBarBrightness: Brightness.light,
  ));

  // Initialize Hive
  try {
    await Hive.initFlutter();
    await Hive.openBox(ApiService.orderBoxName);
    await Hive.openBox(ApiService.syncQueueBoxName);
    await Hive.openBox(ApiService.settingsBoxName);
    debugPrint("Hive boxes opened successfully.");
  } catch (e) {
    debugPrint("Hive failed to open: $e");
  }

  Map<String, dynamic>? authData;
  try {
    await ApiService.initBaseUrl();
    authData = await ApiService().checkAutoLogin();
  } catch (e) {
    debugPrint("Session check failed: $e");
  }

  runApp(GasFlowApp(authData: authData));
}

class GasFlowApp extends StatelessWidget {
  final Map<String, dynamic>? authData;
  const GasFlowApp({super.key, this.authData});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'GasFlow Driver',
      themeMode: ThemeMode.light,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.light,
        // ─── Color Tokens (from design reference) ─────────────────
        colorScheme: const ColorScheme.light(
          primary: Color(0xFF2563EB),       // Primary Action Blue
          onPrimary: Colors.white,
          secondary: Color(0xFF16A34A),     // Success Green
          error: Color(0xFFEF4444),         // Danger Red
          surface: Color(0xFFFFFFFF),       // Card White
          surfaceContainerHighest: Color(0xFFF8FAFC), // Background
          outline: Color(0xFFE2E8F0),       // Border
          onSurface: Color(0xFF0F172A),     // Primary Text
          onSurfaceVariant: Color(0xFF64748B), // Muted Text
        ),
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
        // ─── Typography ───────────────────────────────────────────
        fontFamily: 'Roboto',
        textTheme: const TextTheme(
          titleLarge: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: Color(0xFF0F172A), letterSpacing: -0.5),
          titleMedium: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF0F172A)),
          bodyLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w400, color: Color(0xFF0F172A)),
          bodyMedium: TextStyle(fontSize: 14, fontWeight: FontWeight.w400, color: Color(0xFF0F172A)),
          bodySmall: TextStyle(fontSize: 12, fontWeight: FontWeight.w400, color: Color(0xFF64748B)),
          labelLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white, letterSpacing: 0.5),
          labelSmall: TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: Color(0xFF64748B), letterSpacing: 0.8),
        ),
        // ─── AppBar ───────────────────────────────────────────────
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFFFFFFFF),
          foregroundColor: Color(0xFF0F172A),
          elevation: 0,
          scrolledUnderElevation: 1,
          centerTitle: false,
          titleTextStyle: TextStyle(
            fontSize: 20, fontWeight: FontWeight.w700,
            color: Color(0xFF0F172A), letterSpacing: -0.5,
          ),
          iconTheme: IconThemeData(color: Color(0xFF0F172A)),
          surfaceTintColor: Colors.white,
          shadowColor: Color(0x14000000),
        ),
        // ─── Buttons ──────────────────────────────────────────────
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF2563EB),
            foregroundColor: Colors.white,
            minimumSize: const Size(double.infinity, 54),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: 0.3),
            elevation: 0,
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: const Color(0xFF2563EB),
            side: const BorderSide(color: Color(0xFF2563EB), width: 1.5),
            minimumSize: const Size(double.infinity, 54),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
        ),
        // ─── Input Fields ─────────────────────────────────────────
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFFF8FAFC),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: Color(0xFF2563EB), width: 2),
          ),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
          labelStyle: const TextStyle(color: Color(0xFF64748B), fontSize: 14),
          hintStyle: const TextStyle(color: Color(0xFF94A3B8), fontSize: 14),
        ),
        // ─── Cards ────────────────────────────────────────────────
        cardTheme: CardThemeData(
          color: Colors.white,
          surfaceTintColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: const BorderSide(color: Color(0xFFE2E8F0)),
          ),
          margin: EdgeInsets.zero,
        ),
        // ─── Divider ──────────────────────────────────────────────
        dividerTheme: const DividerThemeData(
          color: Color(0xFFE2E8F0),
          thickness: 1,
          space: 1,
        ),
        // ─── Bottom Nav ───────────────────────────────────────────
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          backgroundColor: Colors.white,
          selectedItemColor: Color(0xFF2563EB),
          unselectedItemColor: Color(0xFF94A3B8),
          showSelectedLabels: true,
          showUnselectedLabels: true,
          type: BottomNavigationBarType.fixed,
          elevation: 0,
          selectedLabelStyle: TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
          unselectedLabelStyle: TextStyle(fontSize: 11, fontWeight: FontWeight.w400),
        ),
        // ─── Chip ─────────────────────────────────────────────────
        chipTheme: ChipThemeData(
          backgroundColor: const Color(0xFFF1F5F9),
          selectedColor: const Color(0xFFDBEAFE),
          labelStyle: const TextStyle(fontSize: 13, color: Color(0xFF0F172A)),
          secondaryLabelStyle: const TextStyle(fontSize: 13, color: Color(0xFF2563EB), fontWeight: FontWeight.w600),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        ),
      ),
      home: authData == null
          ? const LoginScreen()
          : HomeScreen(driverData: authData!['driver'], token: authData!['token']),
    );
  }
}