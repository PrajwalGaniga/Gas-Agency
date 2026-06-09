import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';
import 'login_screen.dart';
import 'profile_screen.dart';

// ─── Design Tokens ───────────────────────────────────────────────────────────
const kBlue       = Color(0xFF2563EB);
const kGreen      = Color(0xFF16A34A);
const kAmber      = Color(0xFFF59E0B);
const kRed        = Color(0xFFEF4444);
const kBg         = Color(0xFFF8FAFC);
const kCard       = Color(0xFFFFFFFF);
const kTextPrimary= Color(0xFF0F172A);
const kTextMuted  = Color(0xFF64748B);
const kBorder     = Color(0xFFE2E8F0);

class HomeScreen extends StatefulWidget {
  final Map driverData;
  final String token;
  const HomeScreen({super.key, required this.driverData, required this.token});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  // ── State ──────────────────────────────────────────────────────────────────
  List orders = [];
  bool isLoading = true;
  Position? currentPos;
  DateTime selectedDate = DateTime.now();
  Timer? _locationTimer;
  Map<String, dynamic>? shiftStatus;
  int pendingSyncCount = 0;
  int _currentTab = 0;

  // ── Tab Animation ──────────────────────────────────────────────────────────
  late AnimationController _tabAnim;

  @override
  void initState() {
    super.initState();
    _tabAnim = AnimationController(vsync: this, duration: const Duration(milliseconds: 300));
    _initDashboard();
    _startLocationPulse();
  }

  @override
  void dispose() {
    _locationTimer?.cancel();
    _tabAnim.dispose();
    super.dispose();
  }

  void _startLocationPulse() {
    _locationTimer = Timer.periodic(const Duration(minutes: 5), (_) async {
      if (currentPos != null) {
        await ApiService().sendLocationPing(widget.token, currentPos!.latitude, currentPos!.longitude);
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
      await ApiService().processSyncQueue(widget.token);
      currentPos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
      final cities = (widget.driverData['cities'] as List).join(',');
      final dateStr = "${selectedDate.year}-${selectedDate.month.toString().padLeft(2, '0')}-${selectedDate.day.toString().padLeft(2, '0')}";
      final res = await ApiService().getOrders(cities, widget.token, currentPos!.latitude, currentPos!.longitude, dateStr);
      final sStatus = await ApiService().getShiftStatus(widget.token);
      final sCount = await ApiService().getSyncQueueCount();
      if (mounted) {
        setState(() {
          orders = res['orders'] ?? [];
          shiftStatus = sStatus;
          pendingSyncCount = sCount;
          isLoading = false;
        });
      }
    } catch (e) {
      debugPrint("Refresh error: $e");
      if (mounted) setState(() => isLoading = false);
    }
  }

  // ── Delivery Complete handler ──────────────────────────────────────────────
  Future<void> _handleComplete(Map order, {int empties = 0, String paymentMode = 'CASH', double amount = 0.0, bool forceUpdate = false}) async {
    setState(() => isLoading = true);
    try {
      final pos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
      final res = await ApiService().completeOrder(widget.token, order['_id'], pos.latitude, pos.longitude, empties, paymentMode, amount, forceUpdate);

      if (mounted && res['prompt_location_update'] == true) {
        setState(() => isLoading = false);
        _showLocationMismatchDialog(order, res['message'] ?? '', empties: empties, paymentMode: paymentMode, amount: amount);
        return;
      }
      setState(() => isLoading = false);
      if (mounted) {
        final success = res['success'] == true;
        _showResultBanner(success ? "Delivery completed! 🎉" : (res['message'] ?? "Failed"), success ? kGreen : kRed);
        if (success) _refreshData();
      }
    } catch (_) {
      if (mounted) setState(() => isLoading = false);
    }
  }

  Future<void> _handleAccept(Map order) async {
    setState(() => isLoading = true);
    final res = await ApiService().acceptOrder(widget.token, order['_id']);
    setState(() => isLoading = false);
    if (mounted) {
      _showResultBanner(res['message'] ?? "Order accepted", res['success'] == true ? kGreen : kRed);
      if (res['success'] == true) _refreshData();
    }
  }

  void _showResultBanner(String msg, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
      backgroundColor: color,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      margin: const EdgeInsets.all(16),
    ));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BUILD
  // ─────────────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final pendingOrders  = orders.where((o) => o['status'] == 'PENDING').toList();
    final activeOrder    = orders.cast<dynamic>().firstWhere((o) => o['status'] == 'IN_PROGRESS', orElse: () => null);
    final deliveredCount = orders.where((o) => o['status'] == 'DELIVERED').length;

    return Scaffold(
      backgroundColor: kBg,
      body: IndexedStack(
        index: _currentTab,
        children: [
          _buildTasksTab(pendingOrders, activeOrder, deliveredCount),
          _buildMapTab(),
          ProfileScreen(driverData: widget.driverData, token: widget.token, shiftStatus: shiftStatus, onLogout: _logout),
        ],
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  // ─── Bottom Navigation ────────────────────────────────────────────────────
  Widget _buildBottomNav() {
    return Container(
      decoration: const BoxDecoration(
        color: kCard,
        border: Border(top: BorderSide(color: kBorder, width: 1)),
      ),
      child: BottomNavigationBar(
        currentIndex: _currentTab,
        onTap: (i) => setState(() => _currentTab = i),
        backgroundColor: Colors.transparent,
        elevation: 0,
        items: [
          BottomNavigationBarItem(
            icon: _navIcon(Icons.check_circle_outline_rounded, 0),
            activeIcon: _navIcon(Icons.check_circle_rounded, 0),
            label: "Tasks",
          ),
          BottomNavigationBarItem(
            icon: _navIcon(Icons.map_outlined, 1),
            activeIcon: _navIcon(Icons.map_rounded, 1),
            label: "Map",
          ),
          BottomNavigationBarItem(
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                _navIcon(Icons.person_outline_rounded, 2),
                if (pendingSyncCount > 0)
                  Positioned(
                    right: -4, top: -4,
                    child: Container(
                      width: 8, height: 8,
                      decoration: const BoxDecoration(color: kAmber, shape: BoxShape.circle),
                    ),
                  ),
              ],
            ),
            activeIcon: _navIcon(Icons.person_rounded, 2),
            label: "Profile",
          ),
        ],
      ),
    );
  }

  Widget _navIcon(IconData icon, int tab) => Icon(icon, color: _currentTab == tab ? kBlue : kTextMuted, size: 24);

  // ─── Tasks Tab (MAIN) ─────────────────────────────────────────────────────
  Widget _buildTasksTab(List pending, dynamic active, int delivered) {
    return CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
        // Header
        SliverToBoxAdapter(child: _buildHeader(delivered, pending.length, active != null)),

        // Active Job Card (if driver has one)
        if (active != null)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: _buildActiveJobCard(active),
            ),
          ),

        // Section label
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Row(
              children: [
                Text(
                  active != null ? "Upcoming Deliveries" : "Today's Deliveries",
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kTextMuted, letterSpacing: 0.5),
                ),
                const Spacer(),
                if (isLoading)
                  const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: kBlue)),
              ],
            ),
          ),
        ),

        // Empty state
        if (orders.isEmpty && !isLoading)
          SliverToBoxAdapter(child: _buildEmptyState()),

        // Orders list
        SliverList(
          delegate: SliverChildBuilderDelegate(
            (ctx, i) {
              final o = (active != null ? pending : orders)[i];
              return Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
                child: _buildOrderCard(o),
              );
            },
            childCount: (active != null ? pending : orders).length,
          ),
        ),
        const SliverToBoxAdapter(child: SizedBox(height: 24)),
      ],
    );
  }

  // ─── Header ───────────────────────────────────────────────────────────────
  Widget _buildHeader(int delivered, int pending, bool hasActive) {
    final name = (widget.driverData['name'] ?? 'Driver').toString().split(' ').first;
    final hour = DateTime.now().hour;
    final greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
    final shiftOpen = shiftStatus?['active'] == true;

    return Container(
      color: kCard,
      padding: const EdgeInsets.fromLTRB(16, 56, 16, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text("$greeting,", style: const TextStyle(fontSize: 13, color: kTextMuted)),
                    const SizedBox(height: 2),
                    Text(name, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: kTextPrimary, letterSpacing: -0.5)),
                  ],
                ),
              ),
              GestureDetector(
                onTap: _refreshData,
                child: Container(
                  width: 40, height: 40,
                  decoration: BoxDecoration(
                    color: isLoading ? kBlue.withOpacity(0.1) : kBg,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: kBorder),
                  ),
                  child: Icon(Icons.refresh_rounded, size: 20, color: isLoading ? kBlue : kTextMuted),
                ),
              ),
            ],
          ),

          const SizedBox(height: 20),

          // Stats Row
          Row(
            children: [
              _statPill("${delivered}", "Delivered", kGreen),
              const SizedBox(width: 8),
              _statPill("${pending}", "Pending", kAmber),
              const SizedBox(width: 8),
              _statPill(shiftOpen ? "${shiftStatus!['inventory']['full_cylinders']}" : "–", "On Truck", kBlue),
              const Spacer(),
              // Date selector
              GestureDetector(
                onTap: () => _pickDate(context),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: kBg, borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: kBorder),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.calendar_today_rounded, size: 13, color: kTextMuted),
                      const SizedBox(width: 4),
                      Text(
                        "${selectedDate.day}/${selectedDate.month}",
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kTextPrimary),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),

          // Shift warning
          if (!shiftOpen) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: kAmber.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: kAmber.withOpacity(0.3)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.warning_amber_rounded, size: 16, color: kAmber),
                  SizedBox(width: 8),
                  Text("No active shift — contact admin to start your shift", style: TextStyle(fontSize: 12, color: kAmber, fontWeight: FontWeight.w500)),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _statPill(String value, String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        children: [
          Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: color)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(fontSize: 10, color: kTextMuted, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  // ─── Active Job Card (Uber-style dominant card) ────────────────────────────
  Widget _buildActiveJobCard(Map order) {
    final distance = (order['distance'] as num?)?.toDouble() ?? 0.0;
    final eta = (distance * 3).ceil(); // rough ETA in minutes

    return Container(
      decoration: BoxDecoration(
        color: kBlue,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [BoxShadow(color: kBlue.withOpacity(0.3), blurRadius: 20, offset: const Offset(0, 8))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Text("ACTIVE DELIVERY", style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Colors.white, letterSpacing: 0.8)),
                ),
              ],
            ),
          ),

          // Customer info
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        order['customer_name'] ?? 'Customer',
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white, letterSpacing: -0.3),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.location_on_rounded, size: 14, color: Colors.white70),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              order['address'] ?? '—',
                              style: const TextStyle(fontSize: 13, color: Colors.white70),
                              maxLines: 1, overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                // Call button
                GestureDetector(
                  onTap: () => launchUrl(Uri.parse("tel:${order['phone']}")),
                  child: Container(
                    width: 44, height: 44,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.call_rounded, color: Colors.white, size: 20),
                  ),
                ),
              ],
            ),
          ),

          // Distance + ETA
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
            child: Row(
              children: [
                _metricChip(Icons.straighten_rounded, "${distance.toStringAsFixed(1)} km"),
                const SizedBox(width: 8),
                _metricChip(Icons.schedule_rounded, "~$eta min"),
              ],
            ),
          ),

          // Action area
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                // Navigate
                Expanded(
                  child: GestureDetector(
                    onTap: () => _launchNav(order['verified_lat'], order['verified_lng']),
                    child: Container(
                      height: 52,
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.white.withOpacity(0.3)),
                      ),
                      child: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.navigation_rounded, color: Colors.white, size: 18),
                          SizedBox(width: 6),
                          Text("Navigate", style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 14)),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                // Complete
                Expanded(
                  flex: 2,
                  child: GestureDetector(
                    onTap: () => _showDeliverySheet(order),
                    child: Container(
                      height: 52,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.check_circle_rounded, color: kBlue, size: 18),
                          SizedBox(width: 6),
                          Text("Complete Delivery", style: TextStyle(color: kBlue, fontWeight: FontWeight.w700, fontSize: 14)),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Report issue link
          GestureDetector(
            onTap: () => _showIssueSheet(order),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: const BoxDecoration(
                color: Color(0x20000000),
                borderRadius: BorderRadius.only(bottomLeft: Radius.circular(20), bottomRight: Radius.circular(20)),
              ),
              child: const Text(
                "⚠ Report Issue",
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.w500),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _metricChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icon, size: 13, color: Colors.white70),
          const SizedBox(width: 4),
          Text(label, style: const TextStyle(fontSize: 12, color: Colors.white, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  // ─── Pending Order Card ────────────────────────────────────────────────────
  Widget _buildOrderCard(Map order) {
    final status = order['status'] ?? 'PENDING';
    final isDelivered = status == 'DELIVERED';
    final distance = (order['distance'] as num?)?.toDouble() ?? 0.0;

    Color statusColor;
    String statusLabel;
    IconData statusIcon;

    switch (status) {
      case 'DELIVERED':
        statusColor = kGreen; statusLabel = "Delivered"; statusIcon = Icons.check_circle_rounded;
        break;
      case 'IN_PROGRESS':
        statusColor = kBlue; statusLabel = "In Progress"; statusIcon = Icons.directions_car_rounded;
        break;
      default:
        statusColor = kAmber; statusLabel = "Pending"; statusIcon = Icons.pending_rounded;
    }

    return Container(
      decoration: BoxDecoration(
        color: kCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kBorder),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Status indicator
                Container(
                  width: 40, height: 40,
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(statusIcon, color: statusColor, size: 20),
                ),
                const SizedBox(width: 12),
                // Customer info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              order['customer_name'] ?? 'Customer',
                              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: kTextPrimary),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: statusColor.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(statusLabel, style: TextStyle(fontSize: 11, color: statusColor, fontWeight: FontWeight.w600)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.location_on_outlined, size: 13, color: kTextMuted),
                          const SizedBox(width: 3),
                          Expanded(
                            child: Text(
                              "${order['address'] ?? '—'} · ${distance.toStringAsFixed(1)} km",
                              style: const TextStyle(fontSize: 12, color: kTextMuted),
                              maxLines: 1, overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                      if (order['city'] != null) ...[
                        const SizedBox(height: 4),
                        Text(order['city'], style: const TextStyle(fontSize: 11, color: kBlue, fontWeight: FontWeight.w500)),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),

          if (!isDelivered) ...[
            const Divider(height: 1, thickness: 1, color: kBorder),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
              child: Row(
                children: [
                  // Call
                  GestureDetector(
                    onTap: () => launchUrl(Uri.parse("tel:${order['phone']}")),
                    child: _iconAction(Icons.call_rounded, "Call", kTextMuted),
                  ),
                  const SizedBox(width: 8),
                  // Navigate
                  if (order['verified_lat'] != null) ...[
                    GestureDetector(
                      onTap: () => _launchNav(order['verified_lat'], order['verified_lng']),
                      child: _iconAction(Icons.near_me_rounded, "Navigate", kBlue),
                    ),
                    const SizedBox(width: 8),
                  ],
                  const Spacer(),
                  // Primary action
                  if (status == 'PENDING')
                    SizedBox(
                      height: 40,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          minimumSize: Size.zero, padding: const EdgeInsets.symmetric(horizontal: 20),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        onPressed: () => _handleAccept(order),
                        child: const Text("Accept", style: TextStyle(fontSize: 13)),
                      ),
                    )
                  else if (status == 'IN_PROGRESS')
                    Row(
                      children: [
                        GestureDetector(
                          onTap: () => _showIssueSheet(order),
                          child: _iconAction(Icons.flag_rounded, "Issue", kRed),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          height: 40,
                          child: ElevatedButton(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: kGreen,
                              minimumSize: Size.zero, padding: const EdgeInsets.symmetric(horizontal: 20),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                            ),
                            onPressed: () => _showDeliverySheet(order),
                            child: const Text("Deliver", style: TextStyle(fontSize: 13, color: Colors.white)),
                          ),
                        ),
                      ],
                    ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _iconAction(IconData icon, String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  // ─── Empty State ──────────────────────────────────────────────────────────
  Widget _buildEmptyState() {
    return Padding(
      padding: const EdgeInsets.all(40),
      child: Column(
        children: [
          Container(
            width: 72, height: 72,
            decoration: BoxDecoration(color: kBorder, borderRadius: BorderRadius.circular(20)),
            child: const Icon(Icons.inbox_rounded, size: 36, color: kTextMuted),
          ),
          const SizedBox(height: 16),
          const Text("All done for today!", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: kTextPrimary)),
          const SizedBox(height: 4),
          const Text("No deliveries assigned. Check back soon.", style: TextStyle(fontSize: 13, color: kTextMuted), textAlign: TextAlign.center),
        ],
      ),
    );
  }

  // ─── Map Tab ──────────────────────────────────────────────────────────────
  Widget _buildMapTab() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          width: 72, height: 72,
          decoration: BoxDecoration(color: kBlue.withOpacity(0.1), borderRadius: BorderRadius.circular(20)),
          child: const Icon(Icons.map_rounded, size: 36, color: kBlue),
        ),
        const SizedBox(height: 20),
        const Text("Map View", style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: kTextPrimary)),
        const SizedBox(height: 8),
        const Text("Open Google Maps to navigate to any delivery.", style: TextStyle(fontSize: 14, color: kTextMuted), textAlign: TextAlign.center),
        const SizedBox(height: 32),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 40),
          child: ElevatedButton.icon(
            onPressed: () {
              final active = orders.cast<dynamic>().firstWhere((o) => o['status'] == 'IN_PROGRESS', orElse: () => null);
              if (active != null) {
                _launchNav(active['verified_lat'], active['verified_lng']);
              } else {
                _showResultBanner("No active delivery to navigate to", kAmber);
              }
            },
            icon: const Icon(Icons.navigation_rounded, size: 18),
            label: const Text("Open Current Delivery"),
          ),
        ),
      ],
    );
  }

  // ─── Delivery Completion Sheet ─────────────────────────────────────────────
  void _showDeliverySheet(Map order) {
    int empties = 1;
    String payMode = "CASH";
    final amountCtrl = TextEditingController(text: order['total_amount']?.toString() ?? "");

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => Container(
          decoration: const BoxDecoration(
            color: kCard,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          padding: EdgeInsets.fromLTRB(24, 20, 24, MediaQuery.of(ctx).viewInsets.bottom + 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Handle
              Center(child: Container(width: 36, height: 4, decoration: BoxDecoration(color: kBorder, borderRadius: BorderRadius.circular(2)))),
              const SizedBox(height: 20),

              const Text("Confirm Delivery", style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: kTextPrimary)),
              Text(order['customer_name'] ?? '', style: const TextStyle(fontSize: 14, color: kTextMuted)),
              const SizedBox(height: 24),

              // Empty cylinders
              const Text("Empty cylinders collected", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kTextPrimary)),
              const SizedBox(height: 10),
              Row(
                children: [0, 1, 2, 3].map((n) => GestureDetector(
                  onTap: () => setS(() => empties = n),
                  child: Container(
                    width: 52, height: 52, margin: const EdgeInsets.only(right: 8),
                    decoration: BoxDecoration(
                      color: empties == n ? kBlue : kBg,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: empties == n ? kBlue : kBorder, width: empties == n ? 2 : 1),
                    ),
                    child: Center(
                      child: Text("$n", style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: empties == n ? Colors.white : kTextPrimary)),
                    ),
                  ),
                )).toList(),
              ),

              const SizedBox(height: 20),

              // Amount
              const Text("Amount collected (₹)", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kTextPrimary)),
              const SizedBox(height: 8),
              TextField(
                controller: amountCtrl,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(prefixIcon: Icon(Icons.currency_rupee_rounded, size: 18, color: kTextMuted)),
              ),

              const SizedBox(height: 20),

              // Payment mode
              const Text("Payment method", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kTextPrimary)),
              const SizedBox(height: 10),
              Row(
                children: ["CASH", "UPI"].map((mode) => GestureDetector(
                  onTap: () => setS(() => payMode = mode),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                    margin: const EdgeInsets.only(right: 10),
                    decoration: BoxDecoration(
                      color: payMode == mode ? kBlue.withOpacity(0.08) : kBg,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: payMode == mode ? kBlue : kBorder, width: payMode == mode ? 1.5 : 1),
                    ),
                    child: Row(
                      children: [
                        Icon(mode == "CASH" ? Icons.payments_rounded : Icons.smartphone_rounded, size: 16, color: payMode == mode ? kBlue : kTextMuted),
                        const SizedBox(width: 6),
                        Text(mode, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: payMode == mode ? kBlue : kTextMuted)),
                      ],
                    ),
                  ),
                )).toList(),
              ),

              const SizedBox(height: 28),

              ElevatedButton(
                onPressed: () {
                  Navigator.pop(ctx);
                  _handleComplete(order, empties: empties, paymentMode: payMode, amount: double.tryParse(amountCtrl.text) ?? 0.0);
                },
                style: ElevatedButton.styleFrom(backgroundColor: kGreen),
                child: const Text("Confirm & Complete"),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Issue Report Sheet ────────────────────────────────────────────────────
  void _showIssueSheet(Map order) {
    String? selected;
    const issues = [
      ("Customer not available", Icons.person_off_rounded),
      ("Wrong address / GPS", Icons.wrong_location_rounded),
      ("Cylinder issue / leak", Icons.warning_rounded),
      ("Customer refused delivery", Icons.block_rounded),
    ];

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => Container(
          decoration: const BoxDecoration(
            color: kCard,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(child: Container(width: 36, height: 4, decoration: BoxDecoration(color: kBorder, borderRadius: BorderRadius.circular(2)))),
              const SizedBox(height: 20),

              const Row(
                children: [
                  Icon(Icons.flag_rounded, color: kRed, size: 20),
                  SizedBox(width: 8),
                  Text("Report Issue", style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: kTextPrimary)),
                ],
              ),
              Text(order['customer_name'] ?? '', style: const TextStyle(fontSize: 14, color: kTextMuted)),
              const SizedBox(height: 20),

              ...issues.map((issue) => GestureDetector(
                onTap: () => setS(() => selected = issue.$1),
                child: Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    color: selected == issue.$1 ? kRed.withOpacity(0.06) : kBg,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: selected == issue.$1 ? kRed : kBorder, width: selected == issue.$1 ? 1.5 : 1),
                  ),
                  child: Row(
                    children: [
                      Icon(issue.$2, size: 18, color: selected == issue.$1 ? kRed : kTextMuted),
                      const SizedBox(width: 12),
                      Text(issue.$1, style: TextStyle(fontSize: 14, color: selected == issue.$1 ? kRed : kTextPrimary, fontWeight: FontWeight.w500)),
                      const Spacer(),
                      if (selected == issue.$1) const Icon(Icons.check_circle_rounded, color: kRed, size: 18),
                    ],
                  ),
                ),
              )),

              const SizedBox(height: 8),
              ElevatedButton(
                onPressed: selected == null ? null : () {
                  Navigator.pop(ctx);
                  _showResultBanner("Issue reported to admin", kAmber);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: selected == null ? kBorder : kRed,
                  disabledBackgroundColor: kBorder,
                ),
                child: const Text("Submit Report"),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Location Mismatch Dialog ──────────────────────────────────────────────
  void _showLocationMismatchDialog(Map order, String msg, {int empties = 0, String paymentMode = 'CASH', double amount = 0.0}) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: kCard,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        contentPadding: EdgeInsets.zero,
        content: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 56, height: 56,
                decoration: BoxDecoration(color: kAmber.withOpacity(0.1), borderRadius: BorderRadius.circular(16)),
                child: const Icon(Icons.wrong_location_rounded, color: kAmber, size: 28),
              ),
              const SizedBox(height: 16),
              const Text("Location Mismatch", style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: kTextPrimary), textAlign: TextAlign.center),
              const SizedBox(height: 8),
              Text(msg, style: const TextStyle(fontSize: 13, color: kTextMuted), textAlign: TextAlign.center),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () {
                  Navigator.pop(ctx);
                  _handleComplete(order, empties: empties, paymentMode: paymentMode, amount: amount, forceUpdate: true);
                },
                child: const Text("Update Location & Complete"),
              ),
              const SizedBox(height: 10),
              OutlinedButton(
                onPressed: () => Navigator.pop(ctx),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: kBorder),
                  foregroundColor: kTextMuted,
                ),
                child: const Text("Cancel"),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────
  Future<void> _pickDate(BuildContext context) async {
    final picked = await showDatePicker(
      context: context, initialDate: selectedDate,
      firstDate: DateTime(2024), lastDate: DateTime.now(),
      builder: (ctx, child) => Theme(
        data: ThemeData.light().copyWith(colorScheme: const ColorScheme.light(primary: kBlue)),
        child: child!,
      ),
    );
    if (picked != null && picked != selectedDate) {
      setState(() => selectedDate = picked);
      _refreshData();
    }
  }

  Future<void> _launchNav(dynamic lat, dynamic lng) async {
    if (lat == null || lng == null) {
      _showResultBanner("Address not verified — cannot navigate", kRed);
      return;
    }
    final gm = "google.navigation:q=$lat,$lng&mode=d";
    final fb = "http://maps.google.com/maps?q=$lat,$lng";
    try {
      if (await canLaunchUrl(Uri.parse(gm))) {
        await launchUrl(Uri.parse(gm));
      } else {
        await launchUrl(Uri.parse(fb), mode: LaunchMode.externalApplication);
      }
    } catch (e) {
      debugPrint("Nav error: $e");
    }
  }

  Future<void> _logout() async {
    await ApiService().logout();
    if (mounted) {
      Navigator.pushAndRemoveUntil(
        context,
        MaterialPageRoute(builder: (_) => const LoginScreen()),
        (_) => false,
      );
    }
  }
}