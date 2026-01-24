import 'dart:async';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';
import 'map_screen.dart';
import 'login_screen.dart'; // 🚀 Add this line
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

  // UX Constants for Consistency
  final Color kBgColor = const Color(0xFF121212); // Deep Dark Background
  final Color kCardColor = const Color(0xFF1E1E1E); // Elevated Surface
  final Color kPrimaryBlue = const Color(0xFF2979FF); // High Vis Blue
  final Color kSuccessGreen = const Color(0xFF00E676); // High Vis Green

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
      context: context, 
      initialDate: selectedDate, 
      firstDate: DateTime(2025), 
      lastDate: DateTime.now(),
      builder: (context, child) {
        // Custom Theme for DatePicker to match Dark Mode
        return Theme(
          data: ThemeData.dark().copyWith(
            colorScheme: ColorScheme.dark(
              primary: kPrimaryBlue,
              onPrimary: Colors.white,
              surface: kCardColor,
            ),
          ),
          child: child!,
        );
      },
    );
    if (picked != null && picked != selectedDate) {
      setState(() => selectedDate = picked);
      _refreshData();
    }
  }

  // 🛰️ DIRECT NAVIGATION ENGINE
  Future<void> _launchNavigation(dynamic lat, dynamic lng) async {
    if (lat == null || lng == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Error: This customer address is not verified yet."))
      );
      return;
    }

    final String googleMapsUrl = "google.navigation:q=$lat,$lng&mode=d";
    final String fallbackUrl = "https://www.google.com/maps/dir/?api=1&destination=$lat,$lng";

    try {
      if (await canLaunchUrl(Uri.parse(googleMapsUrl))) {
        await launchUrl(Uri.parse(googleMapsUrl));
      } else {
        await launchUrl(Uri.parse(fallbackUrl), mode: LaunchMode.externalApplication);
      }
    } catch (e) {
      debugPrint("Could not launch navigation: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    int deliv = orders.where((o) => o['status'] == 'DELIVERED').length;
    int ongoing = orders.where((o) => o['status'] == 'IN_PROGRESS').length;
    int pend = orders.where((o) => o['status'] == 'PENDING').length;

    return Scaffold(
      backgroundColor: kBgColor,
      appBar: AppBar(
  elevation: 0,
  backgroundColor: kCardColor,
  title: const Text(
    "GASFLOW", 
    style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.2, color: Colors.white)
  ),
  actions: [
    IconButton(
      icon: const Icon(Icons.refresh, color: Colors.white), 
      onPressed: _refreshData
    ),
    IconButton(
      icon: const Icon(Icons.logout, color: Colors.redAccent), 
      onPressed: () async {
        // 1. Clear local session data (Token & Driver Info)
        await ApiService().logout();
        
        // 2. 🚀 Redirection: Move back to Login Screen and prevent 'Back' button access
        if (context.mounted) {
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (context) => LoginScreen()), 
      (route) => false,
    );
  }
      },
    ),
  ],
),
      body: Column(
        children: [
          // 1️⃣ DRIVER PERFORMANCE DASHBOARD
          Container(
            padding: const EdgeInsets.fromLTRB(16, 5, 16, 20),
            decoration: BoxDecoration(
              color: kCardColor,
              borderRadius: const BorderRadius.only(bottomLeft: Radius.circular(20), bottomRight: Radius.circular(20)),
              boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.5), blurRadius: 10, offset: const Offset(0, 5))]
            ),
            child: Column(
              children: [
                // Date Selector Row
                InkWell(
                  onTap: () => _selectDate(context),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.calendar_month, color: Colors.white70, size: 20),
                        const SizedBox(width: 8),
                        Text(
                          "${selectedDate.day}/${selectedDate.month}/${selectedDate.year}",
                          style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)
                        ),
                        const Icon(Icons.arrow_drop_down, color: Colors.white70)
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                // Stat Cards
                Row(
                  children: [
                    _statCard("Total", orders.length.toString(), Colors.grey[800]!),
                    const SizedBox(width: 10),
                    _statCard("Done", deliv.toString(), Colors.green[900]!),
                    const SizedBox(width: 10),
                    _statCard("Pending", pend.toString(), Colors.orange[900]!),
                    const SizedBox(width: 10),
                    _statCard("Active", ongoing.toString(), kPrimaryBlue.withOpacity(0.3)),
                  ],
                ),
              ],
            ),
          ),

          // 2️⃣ PRIMARY CTA: MAP VIEW
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 20, 16, 10),
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: kPrimaryBlue,
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 56), // Large tap area
                elevation: 4,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (context) => MapScreen(orders: orders, currentPos: currentPos!))),
              icon: const Icon(Icons.map, size: 28),
              label: const Text("VIEW MAP MODE", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, letterSpacing: 1)),
            ),
          ),

          // 3️⃣ LIST HEADER
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            child: Row(
              children: [
                Text("ORDERS QUEUE", style: TextStyle(color: Colors.grey[400], fontSize: 12, fontWeight: FontWeight.bold)),
                const Spacer(),
                if (isLoading) const SizedBox(width: 15, height: 15, child: CircularProgressIndicator(strokeWidth: 2))
              ],
            ),
          ),

          // 4️⃣ SCROLLABLE ORDER LIST
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refreshData,
              child: ListView.builder(
                padding: const EdgeInsets.only(bottom: 80), // Space for fab or bottom area
                itemCount: orders.length,
                itemBuilder: (context, index) => _buildOrderRow(orders[index], index + 1),
              ),
            ),
          )
        ],
      ),
    );
  }

  Widget _statCard(String label, String val, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: Colors.white10)
        ),
        child: Column(
          children: [
            Text(val, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w900)),
            const SizedBox(height: 4),
            Text(label.toUpperCase(), style: const TextStyle(color: Colors.white70, fontSize: 10, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }

  // 📝 ORDER ROW with INTEGRATED NAV BUTTON
  Widget _buildOrderRow(Map o, int sno) {
    final status = o['status'] ?? 'PENDING';
    Color rowBgColor;
    Color statusColor;

    // Visual Logic: High contrast for outdoor visibility
    switch (status) {
      case 'DELIVERED':
        rowBgColor = const Color(0xFF0F2E14); // Very Dark Green
        statusColor = kSuccessGreen;
        break;
      case 'IN_PROGRESS':
        rowBgColor = const Color(0xFF0D2545); // Very Dark Blue
        statusColor = kPrimaryBlue;
        break;
      default:
        rowBgColor = kCardColor;
        statusColor = Colors.orangeAccent;
    }

    return Card(
      color: rowBgColor,
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: status == 'IN_PROGRESS' 
            ? BorderSide(color: kPrimaryBlue, width: 2) // Active order highlight
            : BorderSide.none
      ),
      child: ExpansionTile(
        initiallyExpanded: status == 'IN_PROGRESS',
        iconColor: Colors.white,
        collapsedIconColor: Colors.grey,
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        
        // 🔹 TITLE ROW
        title: Row(
          children: [
            Text("#$sno", style: TextStyle(color: Colors.grey[500], fontSize: 14, fontWeight: FontWeight.bold)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    o['customer_name'] ?? 'Unknown', 
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                       Icon(Icons.circle, size: 8, color: statusColor),
                       const SizedBox(width: 4),
                       Text(status.replaceAll('_', ' '), style: TextStyle(color: statusColor, fontSize: 11, fontWeight: FontWeight.bold)),
                    ],
                  )
                ],
              )
            ),
            
            // 🚀 THE CRITICAL NAV BUTTON
            if (o['verified_lat'] != null)
              GestureDetector(
                onTap: () => _launchNavigation(o['verified_lat'], o['verified_lng']),
                child: Container(
                  margin: const EdgeInsets.only(left: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: Colors.white, // White button for max contrast against dark theme
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.near_me, color: Colors.black, size: 16),
                      SizedBox(width: 4),
                      Text("NAV", style: TextStyle(color: Colors.black, fontWeight: FontWeight.w900, fontSize: 12)),
                    ],
                  ),
                ),
              ),
          ],
        ),
        
        // 🔹 SUBTITLE (Address)
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(
            children: [
              const Icon(Icons.location_on, size: 14, color: Colors.grey),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  "${o['address']} • ${(o['distance'] ?? 0.0).toStringAsFixed(1)} km",
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Colors.grey, fontSize: 13)
                ),
              ),
            ],
          ),
        ),

        // 🔹 EXPANDED ACTIONS
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              color: Color(0xFF252525), // Slightly lighter internal bg
              borderRadius: BorderRadius.only(bottomLeft: Radius.circular(12), bottomRight: Radius.circular(12))
            ),
            child: Row(
              children: [
                // Call Button
                _actionBtn(Icons.call, Colors.grey[800]!, Colors.white, "Call", () => launchUrl(Uri.parse("tel:${o['phone']}"))),
                const SizedBox(width: 10),
                
                // Dynamic Main Action
                Expanded(
                  child: status == 'PENDING'
                    ? _mainActionBtn("ACCEPT ORDER", Colors.orange[800]!, () => _handleStatusChange(o, 'accept'))
                    : status == 'IN_PROGRESS'
                        ? _mainActionBtn("MARK DELIVERED", kSuccessGreen, () => _handleStatusChange(o, 'complete'))
                        : Container(
                            height: 45,
                            alignment: Alignment.center,
                            decoration: BoxDecoration(border: Border.all(color: Colors.green), borderRadius: BorderRadius.circular(8)),
                            child: const Text("COMPLETED", style: TextStyle(color: Colors.green, fontWeight: FontWeight.bold)),
                          ),
                ),
                
                const SizedBox(width: 10),
                // Edit Button
                _actionBtn(Icons.edit, Colors.grey[800]!, Colors.white, "Edit", () => _showChangeRequest(o)),
              ],
            ),
          )
        ],
      ),
    );
  }

  // 🧱 HELPER WIDGETS FOR BUTTONS
  Widget _actionBtn(IconData icon, Color bg, Color fg, String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      child: Container(
        width: 50, height: 45,
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(8)),
        child: Icon(icon, color: fg, size: 20),
      ),
    );
  }

  Widget _mainActionBtn(String label, Color bg, VoidCallback onTap) {
    return SizedBox(
      height: 45,
      child: ElevatedButton(
        style: ElevatedButton.styleFrom(backgroundColor: bg, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
        onPressed: onTap,
        child: Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
      ),
    );
  }

  // --- LOGIC IMPLEMENTATION (Kept mostly same, added safe checks) ---
  Future<void> _handleStatusChange(Map o, String action) async {
    bool success = false;
    setState(() => isLoading = true); // UX: Show loading during async
    
    if (action == 'accept') {
      final res = await ApiService().acceptOrder(widget.token, o['_id']);
      success = res['success'];
    } else {
      Position pos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
      final res = await ApiService().completeOrder(widget.token, o['_id'], pos.latitude, pos.longitude);
      success = res['success'];
    }
    await _refreshData(); // Refresh list to reflect changes
  }

  void _showChangeRequest(Map order) {
    String cat = "ADDRESS";
    final det = TextEditingController();
    showDialog(context: context, builder: (c) => AlertDialog(
      backgroundColor: kCardColor,
      title: Text("Change Request", style: const TextStyle(color: Colors.white)),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        DropdownButtonFormField(
          value: "ADDRESS", dropdownColor: const Color(0xFF2C2C2C),
          style: const TextStyle(color: Colors.white),
          items: const [
            DropdownMenuItem(value: "ADDRESS", child: Text("Wrong Address")),
            DropdownMenuItem(value: "PHONE", child: Text("New Phone Number"))
          ], 
          onChanged: (v) => cat = v!,
          decoration: const InputDecoration(filled: true, fillColor: Color(0xFF121212)),
        ),
        const SizedBox(height: 15),
        TextField(
          controller: det, style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(labelText: "Correct Details", filled: true, fillColor: Color(0xFF121212)),
        ),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text("Cancel")),
        ElevatedButton(
          style: ElevatedButton.styleFrom(backgroundColor: kPrimaryBlue),
          onPressed: () async {
            await ApiService().submitChangeRequest(widget.token, {
              'customer_id': order['customer_id'], 'category': cat, 'new_details': det.text
            });
            Navigator.pop(context);
            _refreshData();
          }, 
          child: const Text("Submit", style: TextStyle(color: Colors.white))
        ),
      ],
    ));
  }
}