import 'package:flutter/material.dart';
import '../services/api_service.dart';

const kBlue       = Color(0xFF2563EB);
const kGreen      = Color(0xFF16A34A);
const kAmber      = Color(0xFFF59E0B);
const kRed        = Color(0xFFEF4444);
const kBg         = Color(0xFFF8FAFC);
const kCard       = Color(0xFFFFFFFF);
const kTextPrimary= Color(0xFF0F172A);
const kTextMuted  = Color(0xFF64748B);
const kBorder     = Color(0xFFE2E8F0);

class ProfileScreen extends StatelessWidget {
  final Map driverData;
  final String token;
  final Map<String, dynamic>? shiftStatus;
  final VoidCallback onLogout;

  const ProfileScreen({
    super.key,
    required this.driverData,
    required this.token,
    required this.shiftStatus,
    required this.onLogout,
  });

  @override
  Widget build(BuildContext context) {
    final name   = driverData['name'] ?? 'Driver';
    final phone  = driverData['phone_number'] ?? '—';
    final cities = (driverData['cities'] as List?)?.join(', ') ?? '—';
    final shiftOpen = shiftStatus?['active'] == true;

    return Scaffold(
      backgroundColor: kBg,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 8),
              const Text("Profile", style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: kTextPrimary, letterSpacing: -0.5)),
              const SizedBox(height: 20),

              // ── Driver Card ────────────────────────────────────
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: kBlue,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [BoxShadow(color: kBlue.withOpacity(0.25), blurRadius: 20, offset: const Offset(0, 8))],
                ),
                child: Row(
                  children: [
                    Container(
                      width: 56, height: 56,
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Center(
                        child: Text(
                          name.isNotEmpty ? name[0].toUpperCase() : 'D',
                          style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: Colors.white),
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white)),
                          const SizedBox(height: 4),
                          Text(phone, style: const TextStyle(fontSize: 13, color: Colors.white70)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 20),

              // ── Territory ──────────────────────────────────────
              _sectionTitle("Assigned Territory"),
              _infoCard([
                _infoRow(Icons.location_city_rounded, "Cities", cities),
              ]),

              const SizedBox(height: 16),

              // ── Truck Status ───────────────────────────────────
              _sectionTitle("Truck Inventory"),
              shiftOpen
                ? _infoCard([
                    _infoRow(Icons.propane_tank_rounded, "Full Cylinders", "${shiftStatus!['inventory']['full_cylinders']}"),
                    const Divider(height: 1, color: kBorder),
                    _infoRow(Icons.inventory_2_rounded, "Empty Cylinders", "${shiftStatus!['inventory']['empty_cylinders']}"),
                    const Divider(height: 1, color: kBorder),
                    _infoRow(Icons.payments_rounded, "Cash Collected", "₹${(shiftStatus!['financials']['expected_cash'] ?? 0.0).toStringAsFixed(0)}"),
                  ])
                : Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: kCard, borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: kBorder),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.info_outline_rounded, color: kAmber, size: 18),
                        SizedBox(width: 10),
                        Text("Shift not started — contact your admin", style: TextStyle(fontSize: 13, color: kTextMuted)),
                      ],
                    ),
                  ),

              const SizedBox(height: 16),

              // ── Connection Status ──────────────────────────────
              _sectionTitle("Connection"),
              _infoCard([
                _infoRow(
                  Icons.cloud_rounded,
                  "Server",
                  ApiService.baseUrl.contains('10.0.2.2') ? 'Local Dev' : ApiService.baseUrl.contains('ngrok') ? 'Bridge Mode' : 'Cloud',
                ),
              ]),

              const SizedBox(height: 32),

              // ── Logout ─────────────────────────────────────────
              OutlinedButton(
                onPressed: () => _confirmLogout(context),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: kRed, width: 1.5),
                  foregroundColor: kRed,
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.logout_rounded, size: 18),
                    SizedBox(width: 8),
                    Text("Sign Out"),
                  ],
                ),
              ),

              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: kTextMuted, letterSpacing: 1.0),
      ),
    );
  }

  Widget _infoCard(List<Widget> rows) {
    return Container(
      decoration: BoxDecoration(
        color: kCard, borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kBorder),
      ),
      child: Column(children: rows),
    );
  }

  Widget _infoRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          Container(
            width: 32, height: 32,
            decoration: BoxDecoration(color: kBlue.withOpacity(0.08), borderRadius: BorderRadius.circular(8)),
            child: Icon(icon, size: 16, color: kBlue),
          ),
          const SizedBox(width: 12),
          Text(label, style: const TextStyle(fontSize: 14, color: kTextMuted)),
          const Spacer(),
          Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: kTextPrimary)),
        ],
      ),
    );
  }

  void _confirmLogout(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: kCard,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text("Sign Out?", style: TextStyle(fontWeight: FontWeight.w700, color: kTextPrimary)),
        content: const Text("You'll need to sign in again next time.", style: TextStyle(color: kTextMuted, fontSize: 14)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("Cancel", style: TextStyle(color: kTextMuted))),
          ElevatedButton(
            onPressed: () { Navigator.pop(ctx); onLogout(); },
            style: ElevatedButton.styleFrom(backgroundColor: kRed, minimumSize: Size.zero, padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10)),
            child: const Text("Sign Out"),
          ),
        ],
      ),
    );
  }
}
