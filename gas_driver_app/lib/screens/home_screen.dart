import 'dart:async';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';
import 'map_screen.dart';
import 'login_screen.dart';
import 'sync_status_screen.dart';

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
  bool isSyncing = false; // 🔄 New: Tracks background sync status
  Position? currentPos;
  DateTime selectedDate = DateTime.now();
  Timer? _locationTimer;
  Map<String, dynamic>? shiftStatus; // 🚚 New: Tracks current inventory
  int pendingSyncCount = 0; // 🔄 New: Counts items in offline queue

  // UX Constants for Consistency
  final Color kBgColor = const Color(0xFF121212); 
  final Color kCardColor = const Color(0xFF1E1E1E); 
  final Color kPrimaryBlue = const Color(0xFF2979FF); 
  final Color kSuccessGreen = const Color(0xFF00E676); 

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

  // 🛰️ Periodic GPS Heartbeat
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

  // 🔄 REFRESH ENGINE: Now handles Background Sync + Offline Caching
  Future<void> _refreshData() async {
    setState(() {
      isLoading = true;
      isSyncing = true;
    });

    try {
      // 1. First, try to sync any locally saved offline deliveries
      await ApiService().processSyncQueue(widget.token);
      
      // 2. Get GPS
      currentPos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
      
      // 3. Fetch orders (Logic now handles Cache fallback)
      String cities = (widget.driverData['cities'] as List).join(',');
      String dateStr = "${selectedDate.year}-${selectedDate.month}-${selectedDate.day}";
      
      final res = await ApiService().getOrders(
        cities, widget.token, currentPos!.latitude, currentPos!.longitude, dateStr
      );

      // 4. Fetch Shift Status (Inventory)
      final sStatus = await ApiService().getShiftStatus(widget.token);
      
      // 5. Check Sync Queue
      final sCount = await ApiService().getSyncQueueCount();
      
      if (mounted) {
        setState(() {
          orders = res['orders'] ?? [];
          shiftStatus = sStatus;
          pendingSyncCount = sCount;
          isLoading = false;
          isSyncing = false;
        });
      }
    } catch (e) {
      debugPrint("Dashboard Refresh Error: $e");
      if (mounted) setState(() { isLoading = false; isSyncing = false; });
    }
  }

  // --- UI BUILDERS (Preserving your specific layout) ---

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
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("GASFLOW", style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.2, color: Colors.white)),
            if (isSyncing) 
              const Text("Syncing with cloud...", style: TextStyle(fontSize: 10, color: Colors.orangeAccent, fontWeight: FontWeight.bold))
          ],
        ),
        actions: [
          IconButton(
            icon: Icon(
              isSyncing ? Icons.sync : Icons.cloud_sync, 
              color: isSyncing ? Colors.orangeAccent : Colors.white
            ),
            tooltip: 'Sync Status',
            onPressed: () {
              Navigator.push(
                context, 
                MaterialPageRoute(builder: (context) => SyncStatusScreen(token: widget.token))
              ).then((_) => _refreshData());
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white), 
            onPressed: _refreshData,
            tooltip: 'Refresh Data',
          ),
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.redAccent), 
            onPressed: () async {
              await ApiService().logout();
              if (context.mounted) {
                Navigator.pushAndRemoveUntil(
                  context,
                  MaterialPageRoute(builder: (context) => const LoginScreen()), 
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
                InkWell(
                  onTap: () => _selectDate(context),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.calendar_month, color: Colors.white70, size: 20),
                        const SizedBox(width: 8),
                        Text("${selectedDate.day}/${selectedDate.month}/${selectedDate.year}",
                          style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                        const Icon(Icons.arrow_drop_down, color: Colors.white70)
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
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
                backgroundColor: kPrimaryBlue, foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 56),
                elevation: 4, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: () {
                if(orders.isEmpty) {
                   ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("No orders available to map.")));
                   return;
                }
                Navigator.push(context, MaterialPageRoute(builder: (context) => MapScreen(orders: orders, currentPos: currentPos!)));
              },
              icon: const Icon(Icons.map, size: 28),
              label: const Text("VIEW MAP MODE", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, letterSpacing: 1)),
            ),
          ),

          // 1.5️⃣ SHIFT STOCK WIDGET (Enhanced)
          if (shiftStatus != null && shiftStatus!['active'] == true)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [kCardColor, kCardColor.withOpacity(0.8)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.white.withOpacity(0.05)),
                  boxShadow: [
                    BoxShadow(color: Colors.black.withOpacity(0.3), blurRadius: 15, offset: const Offset(0, 8))
                  ]
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text("TRUCK STOCK", style: TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w900, letterSpacing: 1.5)),
                        Row(
                          children: [
                            if (pendingSyncCount > 0)
                              Container(
                                margin: const EdgeInsets.only(right: 8),
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(color: Colors.orangeAccent.withOpacity(0.2), borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.orangeAccent.withOpacity(0.4))),
                                child: Row(
                                  children: [
                                    const Icon(Icons.sync_problem, color: Colors.orangeAccent, size: 10),
                                    const SizedBox(width: 4),
                                    Text("$pendingSyncCount PENDING", style: const TextStyle(color: Colors.orangeAccent, fontSize: 8, fontWeight: FontWeight.bold)),
                                  ],
                                ),
                              ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                              decoration: BoxDecoration(color: Colors.green[900]?.withOpacity(0.3), borderRadius: BorderRadius.circular(20)),
                              child: const Row(
                                children: [
                                  Icon(Icons.check_circle, color: Colors.greenAccent, size: 12),
                                  SizedBox(width: 4),
                                  Text("SHIFT OPEN", style: TextStyle(color: Colors.greenAccent, fontSize: 9, fontWeight: FontWeight.bold)),
                                ],
                              ),
                            ),
                          ],
                        )
                      ],
                    ),
                    const SizedBox(height: 20),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _inventoryItem("LOADED", shiftStatus!['inventory']['total_loaded']?.toString() ?? "0", Icons.add_business, Colors.indigoAccent),
                        _inventoryItem("AVAILABLE", shiftStatus!['inventory']['full_cylinders'].toString(), Icons.propane_tank, Colors.blueAccent),
                        _inventoryItem("EMPTIES", shiftStatus!['inventory']['empty_cylinders'].toString(), Icons.moped, Colors.orangeAccent),
                        _inventoryItem("COLLECTED", "₹${shiftStatus!['financials']['expected_cash'] ?? shiftStatus!['financials']['expected_cash_collected'] ?? 0.0}", Icons.payments, Colors.greenAccent),
                      ],
                    ),
                  ],
                ),
              ),
            ),

          // 3️⃣ LIST HEADER
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            child: Row(
              children: [
                Text("ORDERS QUEUE", style: TextStyle(color: Colors.grey[400], fontSize: 12, fontWeight: FontWeight.bold)),
                const Spacer(),
                if (isLoading) const SizedBox(width: 15, height: 15, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70))
              ],
            ),
          ),

          // 4️⃣ SCROLLABLE ORDER LIST
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refreshData,
              child: orders.isEmpty && !isLoading 
                ? const Center(child: Text("No orders found for this date.", style: TextStyle(color: Colors.grey)))
                : ListView.builder(
                    padding: const EdgeInsets.only(bottom: 80),
                    itemCount: orders.length,
                    itemBuilder: (context, index) => _buildOrderRow(orders[index], index + 1),
                  ),
            ),
          )
        ],
      ),
    );
  }

  // 📝 UPDATED ORDER ROW: Handles Offline Success Feedback & Type Safety
  Widget _buildOrderRow(Map o, int sno) {
    final status = o['status'] ?? 'PENDING';
    Color rowBgColor;
    Color statusColor;

    switch (status) {
      case 'DELIVERED':
        rowBgColor = const Color(0xFF0F2E14); 
        statusColor = kSuccessGreen;
        break;
      case 'IN_PROGRESS':
        rowBgColor = const Color(0xFF0D2545); 
        statusColor = kPrimaryBlue;
        break;
      default:
        rowBgColor = kCardColor;
        statusColor = Colors.orangeAccent;
    }

    // 🕒 OVERDUE CHECK (> 4 hours pending)
    bool isOverdue = false;
    if (status == 'PENDING' && o['created_at'] != null) {
      try {
        DateTime createdAt = DateTime.parse(o['created_at'].toString());
        if (DateTime.now().toUtc().difference(createdAt).inHours >= 4) {
          isOverdue = true;
        }
      } catch (e) {
        // ignore date parse errors
      }
    }

    // 🛡️ PRO-FIX: Safe distance parsing to prevent 'String is not a subtype of double' crash
    double distance = 0.0;
    try {
      var rawDist = o['distance'];
      if (rawDist != null) {
        // This handles cases where rawDist is already a double or a String from cache
        distance = double.tryParse(rawDist.toString()) ?? 0.0;
      }
    } catch (e) {
      distance = 0.0;
    }

    return Card(
      color: rowBgColor,
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: status == 'IN_PROGRESS' ? BorderSide(color: kPrimaryBlue, width: 2) : BorderSide.none
      ),
      child: ExpansionTile(
        initiallyExpanded: status == 'IN_PROGRESS',
        iconColor: Colors.white,
        collapsedIconColor: Colors.grey,
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        title: Row(
          children: [
            Text("#$sno", style: TextStyle(color: Colors.grey[500], fontSize: 14, fontWeight: FontWeight.bold)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(o['customer_name'] ?? 'Unknown', overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Row(children: [
                    Icon(Icons.circle, size: 8, color: statusColor),
                    const SizedBox(width: 4),
                    Text(status.replaceAll('_', ' '), style: TextStyle(color: statusColor, fontSize: 11, fontWeight: FontWeight.bold)),
                    if (o['is_rescheduled'] == true) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.amber[900], 
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: Colors.amber[400]!, width: 0.5)
                        ),
                        child: const Row(
                          children: [
                            Icon(Icons.warning_amber_rounded, size: 10, color: Colors.white),
                            SizedBox(width: 2),
                            Text('RESCHEDULED', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
                          ],
                        ),
                      )
                    ] else if (isOverdue) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(color: Colors.red[900], borderRadius: BorderRadius.circular(4)),
                        child: const Text('DELAYED', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
                      )
                    ]
                  ])
                ],
              )
            ),
            if (o['verified_lat'] != null)
              _navButton(
                // Ensure coordinates are also treated as doubles safely
                double.tryParse(o['verified_lat'].toString()) ?? 0.0, 
                double.tryParse(o['verified_lng'].toString()) ?? 0.0
              ),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(children: [
            const Icon(Icons.location_on, size: 14, color: Colors.grey),
            const SizedBox(width: 4),
            Expanded(child: Text("${o['address']} • ${distance.toStringAsFixed(1)} km",
              maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.grey, fontSize: 13))),
          ]),
        ),
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(color: Color(0xFF252525), borderRadius: BorderRadius.only(bottomLeft: Radius.circular(12), bottomRight: Radius.circular(12))),
            child: Row(
              children: [
                _actionBtn(Icons.call, Colors.grey[800]!, Colors.white, "Call", () => launchUrl(Uri.parse("tel:${o['phone']}"))),
                const SizedBox(width: 10),
                Expanded(
                  child: status == 'PENDING'
                    ? _mainActionBtn("ACCEPT ORDER", Colors.orange[800]!, () => _handleStatusChange(o, 'accept'))
                    : status == 'IN_PROGRESS'
                        ? _mainActionBtn(
                            "MARK DELIVERED", 
                            (shiftStatus?['inventory']?['full_cylinders'] ?? 0) > 0 ? kSuccessGreen : Colors.grey, 
                            () => (shiftStatus?['inventory']?['full_cylinders'] ?? 0) > 0 
                                ? _showDeliveryConfirmation(o) 
                                : ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Insufficient Stock on Truck.")))
                          )
                        : Container(height: 45, alignment: Alignment.center,
                            decoration: BoxDecoration(border: Border.all(color: Colors.green), borderRadius: BorderRadius.circular(8)),
                            child: const Text("COMPLETED", style: TextStyle(color: Colors.green, fontWeight: FontWeight.bold))),
                ),
                const SizedBox(width: 10),
                _actionBtn(Icons.edit, Colors.grey[800]!, Colors.white, "Edit", () => _showChangeRequest(o)),
              ],
            ),
          )
        ],
      ),
    );
  }
  // --- LOGIC HANDLING (Updated for Offline Feedback) ---

  Future<void> _handleStatusChange(Map o, String action, {int empties = 0, String paymentMode = 'CASH', double amountCollected = 0.0}) async {
    setState(() => isLoading = true);
    
    try {
      if (action == 'accept') {
        final res = await ApiService().acceptOrder(widget.token, o['_id']);
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(res['message'] ?? "Order Accepted")));
      } else {
        Position pos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
        final res = await ApiService().completeOrder(widget.token, o['_id'], pos.latitude, pos.longitude, empties, paymentMode, amountCollected);
        
        // 🛡️ OFFLINE FEEDBACK: Tell user if it's saved locally
        if (mounted && res['offline'] == true) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(backgroundColor: Colors.orange, content: Text("No signal. Delivery saved on phone and will sync later."))
          );
        } else if (mounted && res['success'] == false) {
           ScaffoldMessenger.of(context).showSnackBar(SnackBar(backgroundColor: Colors.redAccent, content: Text(res['message'] ?? "Failed to mark delivered.")));
        } else if (mounted && res['success'] == true) {
           ScaffoldMessenger.of(context).showSnackBar(SnackBar(backgroundColor: Colors.green, content: Text(res['message'] ?? "Delivery successful.")));
        }
      }
      _refreshData();
    } catch (e) {
      if (mounted) {
        setState(() => isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Error processing status change.")));
      }
    }
  }

  // --- REUSABLE UI COMPONENTS ---

  Widget _navButton(double lat, double lng) {
    return GestureDetector(
      onTap: () => _launchNavigation(lat, lng),
      child: Container(
        margin: const EdgeInsets.only(left: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8)),
        child: const Row(children: [
          Icon(Icons.near_me, color: Colors.black, size: 16),
          SizedBox(width: 4),
          Text("NAV", style: TextStyle(color: Colors.black, fontWeight: FontWeight.w900, fontSize: 12)),
        ]),
      ),
    );
  }

  Widget _statCard(String label, String val, Color color) {
    return Expanded(child: Container(
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(10), border: Border.all(color: Colors.white10)),
      child: Column(children: [
        Text(val, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w900)),
        const SizedBox(height: 4),
        Text(label.toUpperCase(), style: const TextStyle(color: Colors.white70, fontSize: 10, fontWeight: FontWeight.bold)),
      ]),
    ));
  }

  Widget _actionBtn(IconData icon, Color bg, Color fg, String label, VoidCallback onTap) {
    return InkWell(onTap: onTap,
      child: Container(width: 50, height: 45, decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(8)),
        child: Icon(icon, color: fg, size: 20)));
  }

  Widget _mainActionBtn(String label, Color bg, VoidCallback onTap) {
    return SizedBox(height: 45,
      child: ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: bg, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
        onPressed: onTap, child: Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))));
  }

  Widget _inventoryItem(String label, String value, IconData icon, Color color) {
    return Column(
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
        Text(label, style: TextStyle(color: Colors.grey[500], fontSize: 10, fontWeight: FontWeight.bold)),
      ],
    );
  }

  // (Kept _selectDate and _showChangeRequest the same as your previous version for production reliability)
  Future<void> _selectDate(BuildContext context) async {
    final DateTime? picked = await showDatePicker(context: context, initialDate: selectedDate, firstDate: DateTime(2025), lastDate: DateTime.now(),
      builder: (context, child) => Theme(data: ThemeData.dark().copyWith(colorScheme: ColorScheme.dark(primary: kPrimaryBlue, onPrimary: Colors.white, surface: kCardColor)), child: child!));
    if (picked != null && picked != selectedDate) { setState(() => selectedDate = picked); _refreshData(); }
  }

  void _showChangeRequest(Map order) {
    String cat = "ADDRESS";
    final det = TextEditingController();
    showDialog(context: context, builder: (c) => AlertDialog(backgroundColor: kCardColor,
      title: const Text("Change Request", style: TextStyle(color: Colors.white)),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        DropdownButtonFormField(value: "ADDRESS", dropdownColor: const Color(0xFF2C2C2C), style: const TextStyle(color: Colors.white),
          items: const [DropdownMenuItem(value: "ADDRESS", child: Text("Wrong Address")), DropdownMenuItem(value: "PHONE", child: Text("New Phone Number"))],
          onChanged: (v) => cat = v.toString(), decoration: const InputDecoration(filled: true, fillColor: Color(0xFF121212))),
        const SizedBox(height: 15),
        TextField(controller: det, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: "Correct Details", filled: true, fillColor: Color(0xFF121212))),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text("Cancel")),
        ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: kPrimaryBlue), onPressed: () async {
          await ApiService().submitChangeRequest(widget.token, {'customer_id': order['customer_id'], 'category': cat, 'new_details': det.text});
          if(mounted) Navigator.pop(context);
          _refreshData();
        }, child: const Text("Submit", style: TextStyle(color: Colors.white))),
      ],
    ));
  }

  void _showDeliveryConfirmation(Map order) {
    int emptiesCollected = 0;
    String paymentMode = "CASH";
    final emptiesController = TextEditingController(text: "1");
    // Ensure accurate price defaulting or set to empty if 0
    final initialAmount = order['total_amount']?.toString() ?? "1000";
    final amountController = TextEditingController(text: initialAmount);

    showDialog(context: context, builder: (c) {
      return StatefulBuilder(
        builder: (context, setStateDialog) {
          return AlertDialog(
            backgroundColor: kCardColor,
            title: const Text("Confirm Delivery", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            content: SingleChildScrollView(
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text("Empties Collected", style: TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 8),
                TextField(
                  controller: emptiesController,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    filled: true, fillColor: Color(0xFF121212),
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 15),
                const Text("Amount Collected (₹)", style: TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 8),
                TextField(
                  controller: amountController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    filled: true, fillColor: Color(0xFF121212),
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 15),
                const Text("Payment Method", style: TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  value: paymentMode,
                  dropdownColor: const Color(0xFF2C2C2C),
                  style: const TextStyle(color: Colors.white),
                  items: const [
                    DropdownMenuItem(value: "CASH", child: Text("Cash (INR)")),
                    DropdownMenuItem(value: "UPI", child: Text("UPI / Online")),
                  ],
                  onChanged: (v) => setStateDialog(() => paymentMode = v!),
                  decoration: const InputDecoration(filled: true, fillColor: Color(0xFF121212), border: OutlineInputBorder()),
                ),
              ]),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text("Cancel", style: TextStyle(color: Colors.grey))),
              ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: kSuccessGreen), 
                onPressed: () {
                  int parsedEmpties = int.tryParse(emptiesController.text) ?? 0;
                  double parsedAmount = double.tryParse(amountController.text) ?? 1000.0;
                  Navigator.pop(context);
                  _handleStatusChange(order, 'complete', empties: parsedEmpties, paymentMode: paymentMode, amountCollected: parsedAmount);
                }, 
                child: const Text("CONFIRM", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold))
              ),
            ],
          );
        }
      );
    });
  }

  Future<void> _launchNavigation(dynamic lat, dynamic lng) async {
    if (lat == null || lng == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Error: Address not verified.")));
      return;
    }
    final String googleMapsUrl = "google.navigation:q=$lat,$lng&mode=d";
    try {
      if (await canLaunchUrl(Uri.parse(googleMapsUrl))) { await launchUrl(Uri.parse(googleMapsUrl)); }
      else { await launchUrl(Uri.parse("http://maps.google.com/maps?q=$lat,$lng"), mode: LaunchMode.externalApplication); }
    } catch (e) { debugPrint("Nav Error: $e"); }
  }
}