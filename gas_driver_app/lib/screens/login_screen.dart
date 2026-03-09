import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'home_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  _LoginScreenState createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLoading = false;
  bool _rememberMe = true; // Added Remember Me toggle state

  // _handleLogin function remains the same, omitted changing to save space, but keeping it structurally identical
  Future<void> _handleLogin() async {
    if (_phoneController.text.isEmpty || _passwordController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please fill all fields")),
      );
      return;
    }

    setState(() => _isLoading = true);
    
    try {
      final res = await ApiService().login(_phoneController.text, _passwordController.text);
      if (mounted) setState(() => _isLoading = false);

      if (res['success'] == true && res['access_token'] != null && res['driver'] != null) {
        if (_rememberMe) {
          await ApiService().saveSession(
            res['access_token'].toString(), 
            res['driver'] as Map<String, dynamic>
          );
        }

        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (context) => HomeScreen(
                driverData: res['driver'],
                token: res['access_token'].toString(),
              ),
            ),
          );
        }
      } else {
        String msg = res['message'] ?? "Login Failed: Server returned error";
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.red[900]));
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Critical Connection Error: ${ApiService.baseUrl}"), backgroundColor: Colors.red[900])
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF0F172A), Color(0xFF1E1B4B)], // Deep Navy to Midnight Purple
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Logo
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: Theme.of(context).primaryColor.withOpacity(0.1),
                    ),
                    child: Icon(Icons.local_shipping, size: 80, color: Theme.of(context).primaryColor),
                  ),
                  const SizedBox(height: 32),
                  
                  // Text
                  const Text(
                    "GasFlow", 
                    style: TextStyle(fontSize: 40, fontWeight: FontWeight.w900, color: Colors.white, letterSpacing: -1),
                  ),
                  const Text(
                    "Fleet Operations Portal", 
                    style: TextStyle(fontSize: 16, color: Colors.white70, letterSpacing: 1.5),
                  ),
                  const SizedBox(height: 48),
                  
                  // Form Fields
                  TextField(
                    controller: _phoneController, 
                    keyboardType: TextInputType.phone,
                    style: const TextStyle(color: Colors.white, fontSize: 18),
                    decoration: const InputDecoration(
                      labelText: "Phone Number", 
                      prefixIcon: Icon(Icons.phone_android, color: Colors.white70),
                    ),
                  ),
                  const SizedBox(height: 20),
                  
                  TextField(
                    controller: _passwordController, 
                    obscureText: true, 
                    style: const TextStyle(color: Colors.white, fontSize: 18),
                    decoration: const InputDecoration(
                      labelText: "Security PIN", 
                      prefixIcon: Icon(Icons.lock_outline, color: Colors.white70),
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Remember Me / Biometric Row
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          SizedBox(
                            width: 24,
                            child: Checkbox(
                              value: _rememberMe,
                              onChanged: (val) => setState(() => _rememberMe = val ?? true),
                              activeColor: Theme.of(context).primaryColor,
                            ),
                          ),
                          const SizedBox(width: 8),
                          const Text("Remember me", style: TextStyle(color: Colors.white70)),
                        ],
                      ),
                      IconButton(
                        icon: const Icon(Icons.fingerprint, color: Colors.white54, size: 32),
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text("Biometric login unlocked in Pro Version"))
                          );
                        },
                      )
                    ],
                  ),
                  
                  const SizedBox(height: 40),
                  
                  // Huge Button
                  _isLoading 
                    ? const CircularProgressIndicator(color: Colors.white) 
                    : ElevatedButton(
                        onPressed: _handleLogin, 
                        child: const Text("ACCESS FLEET")
                      ),
                  
                  const SizedBox(height: 24),
                  
                  // Debug/Status Indicator
                  Text(
                    "Service Status: ${ApiService.baseUrl.contains('10.0.2.2') ? 'Local Dev' : ApiService.baseUrl.contains('ngrok') ? 'Bridge Mode' : 'Cloud'}",
                    style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}