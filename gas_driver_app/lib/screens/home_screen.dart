import 'dart:async';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';
import 'map_screen.dart';

class HomeScreen extends StatefulWidget {
  final Map driverData;
  final String token;
  const HomeScreen({super.key, required this.driverData, required this.token});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List orders = [];
  bool isLoading = true;
  Position? currentPos;
  DateTime selectedDate = DateTime.now();
  Timer? _locationTimer;

  @override
  void initState() {
    super.initState();
    _initDashboard();
    _startLocationPulse(); 
  }

  @override
  void dispose() {
    _locationTimer?.cancel();
    super.dispose();
  }

  // 🛰️ Heartbeat to feed 'Work Hours' on Admin Dashboard
  void _startLocationPulse() {
    _locationTimer = Timer.periodic(const Duration(minutes: 5), (timer) async {
      if (currentPos != null) {
        await ApiService().sendLocationPing(
          widget.token, currentPos!.latitude, currentPos!.longitude
        );
      }
    });
  }

  Future<void> _initDashboard() async {
    LocationPermission p = await Geolocator.checkPermission();
    if (p == LocationPermission.denied) await Geolocator.requestPermission();
    _refreshData();
  }

  Future<void> _refreshData() async {
    setState(() => isLoading = true);
    try {
      currentPos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
      String cities = (widget.driverData['cities'] as List).join(',');
      // Standardize date format for Python backend
      String dateStr = "${selectedDate.year}-${selectedDate.month}-${selectedDate.day}";
      
      final res = await ApiService().getOrders(
        cities, widget.token, currentPos!.latitude, currentPos!.longitude, dateStr
      );
      
      setState(() {
        orders = res['orders'] ?? [];
        isLoading = false;
      });
    } catch (e) {
      debugPrint("Load Error: $e");
      setState(() => isLoading = false);
    }
  }

  Future<void> _selectDate(BuildContext context) async {
    final DateTime? picked = await showDatePicker(
      context: context, initialDate: selectedDate, firstDate: DateTime(2025), lastDate: DateTime.now(),
    );
    if (picked != null && picked != selectedDate) {
      setState(() => selectedDate = picked);
      _refreshData();
    }
  }

  @override
  Widget build(BuildContext context) {
    int deliv = orders.where((o) => o['status'] == 'DELIVERED').length;
    int ongoing = orders.where((o) => o['status'] == 'IN_PROGRESS').length;
    int pend = orders.where((o) => o['status'] == 'PENDING').length;

    return Scaffold(
      backgroundColor: const Color(0xFF121212), // Sleek Dark Theme
      appBar: AppBar(
        title: const Text("GasFlow Driver Portal", style: TextStyle(fontWeight: FontWeight.w900)),
        backgroundColor: const Color(0xFF0D47A1),
        foregroundColor: Colors.white,
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _refreshData),
          IconButton(icon: const Icon(Icons.logout), onPressed: () => ApiService().logout()),
        ],
      ),
      body: Column(
        children: [
          // 📊 HEADER: Dashboard Stats
          Container(
            padding: const EdgeInsets.all(20),
            color: const Color(0xFF1E1E1E),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text("Date: ${selectedDate.day}/${selectedDate.month}/${selectedDate.year}", 
                      style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                    IconButton(icon: const Icon(Icons.calendar_today, color: Colors.white, size: 20), onPressed: () => _selectDate(context)),
                  ],
                ),
                const SizedBox(height: 15),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _statBox("Total", orders.length.toString(), Colors.grey[800]!),
                    _statBox("Delivered", deliv.toString(), Colors.green[900]!),
                    _statBox("Pending", pend.toString(), Colors.orange[900]!),
                    _statBox("Ongoing", ongoing.toString(), Colors.blue[900]!),
                  ],
                ),
              ],
            ),
          ),
          
          // 🗺️ NAVIGATION BUTTON
          Padding(
            padding: const EdgeInsets.all(12),
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF2C2C2C), minimumSize: const Size(double.infinity, 55),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8), side: const BorderSide(color: Colors.white12))
              ),
              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (context) => MapScreen(orders: orders, currentPos: currentPos!))),
              icon: const Icon(Icons.map_outlined, color: Colors.blueAccent),
              label: const Text("VIEW ALL ON MAP", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            ),
          ),

          // 📜 CHECKLIST HEADER
          Container(
            width: double.infinity, padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 15),
            color: const Color(0xFF263238),
            child: const Text("Today's Work List", style: TextStyle(color: Colors.white70, fontWeight: FontWeight.w900, fontSize: 12)),
          ),

          // 📋 THE DYNAMIC STATUS TABLE
          Expanded(
            child: isLoading 
              ? const Center(child: CircularProgressIndicator())
              : ListView.builder(
                  itemCount: orders.length,
                  itemBuilder: (context, index) => _buildOrderRow(orders[index], index + 1),
                ),
          )
        ],
      ),
    );
  }

  Widget _buildOrderRow(Map o, int sno) {
    final status = o['status'] ?? 'PENDING';
    Color rowColor;
    
    // 🎨 Logic: High-Contrast Color Categorization
    switch (status) {
      case 'DELIVERED':
        rowColor = const Color(0xFF1B5E20).withOpacity(0.4); // Dark Green
        break;
      case 'IN_PROGRESS':
        rowColor = const Color(0xFF0D47A1).withOpacity(0.4); // Dark Blue
        break;
      default:
        rowColor = const Color(0xFF424242).withOpacity(0.4); // Grey/Orange Tint
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 1),
      decoration: BoxDecoration(color: rowColor, border: const Border(bottom: BorderSide(color: Colors.white10, width: 0.5))),
      child: ExpansionTile(
        initiallyExpanded: status == 'IN_PROGRESS',
        iconColor: Colors.white, collapsedIconColor: Colors.white38,
        title: Row(
          children: [
            Text("$sno.", style: const TextStyle(color: Colors.white54, fontSize: 12)),
            const SizedBox(width: 10),
            Expanded(child: Text(o['customer_name'] ?? 'N/A', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
            _statusBadge(status),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(left: 22),
          child: Text("${o['address']} • ${(o['distance'] ?? 0.0).toStringAsFixed(1)}km", 
            style: const TextStyle(color: Colors.white38, fontSize: 11)),
        ),
        children: [
          Container(
            color: const Color(0xFF1E1E1E),
            padding: const EdgeInsets.all(15),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _actionBtn("Call", Icons.phone, Colors.blue[700]!, () => launchUrl(Uri.parse("tel:${o['phone']}"))),
                
                // 🚀 Functional Lifecycle: Accept -> Complete
                if (status == 'PENDING')
                  _actionBtn("Accept Order", Icons.play_arrow, Colors.orange[800]!, () => _handleStatusChange(o, 'accept'))
                else if (status == 'IN_PROGRESS')
                  _actionBtn("Mark Delivered", Icons.check_circle, Colors.green[700]!, () => _handleStatusChange(o, 'complete'))
                else
                  const Text("Delivered ✅", style: TextStyle(color: Colors.green, fontWeight: FontWeight.bold)),

                _actionBtn("Change Req", Icons.edit_note, Colors.grey[700]!, () => _showChangeRequest(o)),
              ],
            ),
          )
        ],
      ),
    );
  }

  // --- 🔥 LOGIC IMPLEMENTATION ---

  Future<void> _handleStatusChange(Map o, String action) async {
    bool success = false;
    if (action == 'accept') {
      final res = await ApiService().acceptOrder(widget.token, o['_id']);
      success = res['success'];
    } else {
      Position pos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
      final res = await ApiService().completeOrder(widget.token, o['_id'], pos.latitude, pos.longitude);
      success = res['success'];
    }
    if (success) _refreshData();
  }

  // 🚀 FIXED: Full Implementation of the Change Request Dialog
  void _showChangeRequest(Map order) {
    String cat = "ADDRESS";
    final det = TextEditingController();
    showDialog(context: context, builder: (c) => AlertDialog(
      backgroundColor: const Color(0xFF1E1E1E),
      title: Text("Change Request: ${order['customer_name']}", style: const TextStyle(color: Colors.white)),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        DropdownButtonFormField(
          value: "ADDRESS", dropdownColor: const Color(0xFF2C2C2C),
          style: const TextStyle(color: Colors.white),
          items: const [
            DropdownMenuItem(value: "ADDRESS", child: Text("Wrong Address/Landmark")),
            DropdownMenuItem(value: "PHONE", child: Text("New Phone Number"))
          ], 
          onChanged: (v) => cat = v!,
          decoration: const InputDecoration(labelText: "Category", labelStyle: TextStyle(color: Colors.white60)),
        ),
        const SizedBox(height: 15),
        TextField(
          controller: det, style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(labelText: "Enter Correct Details", labelStyle: TextStyle(color: Colors.white60), border: OutlineInputBorder()),
        ),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text("Cancel")),
        ElevatedButton(onPressed: () async {
          await ApiService().submitChangeRequest(widget.token, {
            'customer_id': order['customer_id'], 'category': cat, 'new_details': det.text
          });
          Navigator.pop(context);
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Request sent to Admin!")));
        }, child: const Text("Submit Request")),
      ],
    ));
  }

  // --- 🎨 UI WIDGETS ---

  Widget _statusBadge(String status) {
    Color bg = Colors.grey[800]!;
    String label = "Pending";
    if (status == 'DELIVERED') { bg = Colors.green[800]!; label = "Delivered"; }
    if (status == 'IN_PROGRESS') { bg = Colors.blue[800]!; label = "Ongoing"; }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(4)),
      child: Text(label, style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
    );
  }

  Widget _statBox(String label, String val, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    decoration: BoxDecoration(color: color.withOpacity(0.2), borderRadius: BorderRadius.circular(8), border: Border.all(color: color.withOpacity(0.4))),
    child: Column(children: [Text(label, style: const TextStyle(color: Colors.white54, fontSize: 9)), Text(val, style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w900))]),
  );

  Widget _actionBtn(String label, IconData icon, Color color, VoidCallback onTap) => ElevatedButton.icon(
    onPressed: onTap, icon: Icon(icon, size: 14), label: Text(label, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold)),
    style: ElevatedButton.styleFrom(backgroundColor: color, foregroundColor: Colors.white, padding: const EdgeInsets.symmetric(horizontal: 10)),
  );
}