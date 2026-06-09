import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/api_service.dart';
import 'home_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> with SingleTickerProviderStateMixin {
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLoading = false;
  bool _rememberMe = true;
  bool _obscurePin = true;
  late AnimationController _animController;
  late Animation<double> _fadeAnim;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(vsync: this, duration: const Duration(milliseconds: 700));
    _fadeAnim = CurvedAnimation(parent: _animController, curve: Curves.easeOut);
    _animController.forward();
  }

  @override
  void dispose() {
    _animController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    if (_phoneController.text.isEmpty || _passwordController.text.isEmpty) {
      _showError("Please enter your phone number and PIN.");
      return;
    }
    setState(() => _isLoading = true);
    try {
      final res = await ApiService().login(_phoneController.text, _passwordController.text);
      if (mounted) setState(() => _isLoading = false);

      if (res['success'] == true && res['access_token'] != null && res['driver'] != null) {
        if (_rememberMe) {
          await ApiService().saveSession(res['access_token'].toString(), res['driver'] as Map<String, dynamic>);
        }
        if (mounted) {
          Navigator.pushReplacement(
            context,
            PageRouteBuilder(
              pageBuilder: (_, __, ___) => HomeScreen(driverData: res['driver'], token: res['access_token'].toString()),
              transitionDuration: const Duration(milliseconds: 400),
              transitionsBuilder: (_, anim, __, child) => FadeTransition(opacity: anim, child: child),
            ),
          );
        }
      } else {
        _showError(res['message'] ?? "Login failed. Please check your credentials.");
      }
    } catch (e) {
      if (mounted) setState(() => _isLoading = false);
      _showError("Cannot connect to server. Check your internet connection.");
    }
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(children: [
          const Icon(Icons.error_outline, color: Colors.white, size: 18),
          const SizedBox(width: 8),
          Expanded(child: Text(msg, style: const TextStyle(fontSize: 13))),
        ]),
        backgroundColor: const Color(0xFFEF4444),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        margin: const EdgeInsets.all(16),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      body: FadeTransition(
        opacity: _fadeAnim,
        child: SafeArea(
          child: SingleChildScrollView(
            physics: const ClampingScrollPhysics(),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 48),

                  // ── Brand Mark ────────────────────────────────────
                  Center(
                    child: Column(
                      children: [
                        Container(
                          width: 72,
                          height: 72,
                          decoration: BoxDecoration(
                            color: const Color(0xFF2563EB),
                            borderRadius: BorderRadius.circular(20),
                            boxShadow: [
                              BoxShadow(
                                color: const Color(0xFF2563EB).withOpacity(0.3),
                                blurRadius: 20,
                                offset: const Offset(0, 8),
                              ),
                            ],
                          ),
                          child: const Icon(Icons.local_shipping_rounded, color: Colors.white, size: 36),
                        ),
                        const SizedBox(height: 20),
                        const Text(
                          "GasFlow",
                          style: TextStyle(
                            fontSize: 32, fontWeight: FontWeight.w800,
                            color: Color(0xFF0F172A), letterSpacing: -1.2,
                          ),
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          "Driver Portal",
                          style: TextStyle(fontSize: 14, color: Color(0xFF64748B), fontWeight: FontWeight.w500),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 52),

                  // ── Form ──────────────────────────────────────────
                  const Text("Phone Number", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF374151))),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _phoneController,
                    keyboardType: TextInputType.phone,
                    style: const TextStyle(fontSize: 16, color: Color(0xFF0F172A), fontWeight: FontWeight.w500),
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    decoration: const InputDecoration(
                      prefixIcon: Icon(Icons.phone_outlined, color: Color(0xFF64748B), size: 20),
                      hintText: "Enter your phone number",
                    ),
                  ),

                  const SizedBox(height: 20),

                  const Text("Security PIN", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF374151))),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _passwordController,
                    obscureText: _obscurePin,
                    style: const TextStyle(fontSize: 16, color: Color(0xFF0F172A), fontWeight: FontWeight.w500),
                    decoration: InputDecoration(
                      prefixIcon: const Icon(Icons.lock_outline_rounded, color: Color(0xFF64748B), size: 20),
                      hintText: "Enter your PIN",
                      suffixIcon: IconButton(
                        icon: Icon(
                          _obscurePin ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                          color: const Color(0xFF64748B), size: 20,
                        ),
                        onPressed: () => setState(() => _obscurePin = !_obscurePin),
                      ),
                    ),
                    onSubmitted: (_) => _handleLogin(),
                  ),

                  const SizedBox(height: 16),

                  // ── Remember Me ───────────────────────────────────
                  Row(
                    children: [
                      SizedBox(
                        width: 22, height: 22,
                        child: Checkbox(
                          value: _rememberMe,
                          onChanged: (v) => setState(() => _rememberMe = v ?? true),
                          activeColor: const Color(0xFF2563EB),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                          side: const BorderSide(color: Color(0xFFCBD5E1), width: 1.5),
                        ),
                      ),
                      const SizedBox(width: 10),
                      const Text("Keep me signed in", style: TextStyle(fontSize: 13, color: Color(0xFF64748B))),
                    ],
                  ),

                  const SizedBox(height: 32),

                  // ── Login Button ──────────────────────────────────
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 200),
                    child: _isLoading
                        ? Container(
                            width: double.infinity, height: 54,
                            decoration: BoxDecoration(
                              color: const Color(0xFF2563EB).withOpacity(0.8),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: const Center(
                              child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5)),
                            ),
                          )
                        : ElevatedButton(
                            onPressed: _handleLogin,
                            child: const Text("Sign In"),
                          ),
                  ),

                  const SizedBox(height: 48),

                  // ── Footer ────────────────────────────────────────
                  Center(
                    child: Text(
                      "${ApiService.baseUrl.contains('10.0.2.2') ? '🟡 Local Dev' : ApiService.baseUrl.contains('ngrok') ? '🔵 Bridge' : '🟢 Cloud'} · Tap here if connection issues",
                      style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}