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
    final res = await ApiService().login(_phoneController.text, _passwordController.text);
    setState(() => _isLoading = false);

    if (res['success'] == true) {
      // 🚀 SUCCESS: Move to Home Screen and pass the driver data + token
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (context) => HomeScreen(
            driverData: res['driver'],
            token: res['access_token'],
          ),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(res['message'] ?? "Login Failed")),
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