import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'login_screen.dart';

const kBlue       = Color(0xFF2563EB);
const kTextMuted  = Color(0xFF64748B);
const kBorder     = Color(0xFFE2E8F0);
const kCard       = Color(0xFFFFFFFF);

class SyncStatusScreen extends StatefulWidget {
  final String token;
  const SyncStatusScreen({super.key, required this.token});

  @override
  State<SyncStatusScreen> createState() => _SyncStatusScreenState();
}

class _SyncStatusScreenState extends State<SyncStatusScreen> {
  int _pendingCount = 0;
  bool _isSyncing = false;

  @override
  void initState() {
    super.initState();
    _loadCount();
  }

  Future<void> _loadCount() async {
    final c = await ApiService().getSyncQueueCount();
    if (mounted) setState(() => _pendingCount = c);
  }

  Future<void> _forceSync() async {
    setState(() => _isSyncing = true);
    await ApiService().processSyncQueue(widget.token);
    await _loadCount();
    if (mounted) setState(() => _isSyncing = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text("Sync Status"),
        leading: const BackButton(),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: kCard,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: kBorder),
              ),
              child: Row(
                children: [
                  Container(
                    width: 48, height: 48,
                    decoration: BoxDecoration(
                      color: _pendingCount == 0 ? const Color(0xFF16A34A).withOpacity(0.1) : kBlue.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      _pendingCount == 0 ? Icons.cloud_done_rounded : Icons.cloud_upload_rounded,
                      color: _pendingCount == 0 ? const Color(0xFF16A34A) : kBlue,
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _pendingCount == 0 ? "All Synced" : "$_pendingCount Pending",
                          style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: Color(0xFF0F172A)),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _pendingCount == 0 ? "All deliveries are synced to the server." : "Deliveries saved offline. Tap sync to upload.",
                          style: const TextStyle(fontSize: 13, color: kTextMuted),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _isSyncing ? null : _forceSync,
              icon: _isSyncing
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.sync_rounded, size: 18),
              label: Text(_isSyncing ? "Syncing..." : "Sync Now"),
            ),
          ],
        ),
      ),
    );
  }
}
