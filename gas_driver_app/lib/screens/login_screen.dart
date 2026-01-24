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
    setState(() => _isLoading = false);

    // 🛡️ SENIOR SAFETY CHECK: Ensure token and driver data are actually present
    if (res['success'] == true && res['access_token'] != null && res['driver'] != null) {
      
      // Save the session to local storage for auto-login
      await ApiService().saveSession(
        res['access_token'].toString(), 
        res['driver'] as Map<String, dynamic>
      );

      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (context) => HomeScreen(
              driverData: res['driver'],
              token: res['access_token'].toString(), // Force to string safely
            ),
          ),
        );
      }
    } else {
      String msg = res['message'] ?? "Login Failed: Server returned incomplete data";
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    }
  } catch (e) {
    setState(() => _isLoading = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text("Connection Error: Server might be waking up. Try again in 30 seconds."))
    );
  }
}

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 100),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.local_gas_station, size: 100, color: Colors.indigo),
              const SizedBox(height: 20),
              const Text("GasFlow Driver", 
                style: TextStyle(fontSize: 32, fontWeight: FontWeight.w900, color: Colors.indigo)),
              const Text("Logistics Management System", 
                style: TextStyle(fontSize: 14, color: Colors.grey)),
              const SizedBox(height: 50),
              TextField(
                controller: _phoneController, 
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: "Phone Number", 
                  prefixIcon: Icon(Icons.phone),
                  border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(15)))
                ),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _passwordController, 
                obscureText: true, 
                decoration: const InputDecoration(
                  labelText: "Password", 
                  prefixIcon: Icon(Icons.lock),
                  border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(15)))
                ),
              ),
              const SizedBox(height: 40),
              _isLoading 
                ? const CircularProgressIndicator() 
                : ElevatedButton(
                    onPressed: _handleLogin, 
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 60), 
                      backgroundColor: Colors.indigo,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15))
                    ),
                    child: const Text("LOGIN TO FLEET", 
                      style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold))
                  )
            ],
          ),
        ),
      ),
    );
  }
}