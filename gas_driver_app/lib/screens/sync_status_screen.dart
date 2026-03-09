import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import '../services/api_service.dart';

class SyncStatusScreen extends StatefulWidget {
  final String token;
  const SyncStatusScreen({super.key, required this.token});

  @override
  State<SyncStatusScreen> createState() => _SyncStatusScreenState();
}

class _SyncStatusScreenState extends State<SyncStatusScreen> {
  final Box _syncBox = Hive.box(ApiService.syncQueueBoxName);
  bool _isSyncing = false;

  void _manualSync() async {
    setState(() => _isSyncing = true);
    
    // Attempt background sync logic from ApiService
    await ApiService().processSyncQueue(widget.token);
    
    setState(() => _isSyncing = false);
    
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Sync cycle complete.")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Offline Sync Status'),
      ),
      body: ValueListenableBuilder(
        valueListenable: _syncBox.listenable(),
        builder: (context, Box box, _) {
          final pendingCount = box.length;
          
          return Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const Spacer(),
                Icon(
                  pendingCount > 0 ? Icons.cloud_off : Icons.cloud_done,
                  size: 100,
                  color: pendingCount > 0 ? Colors.amber : Colors.green,
                ),
                const SizedBox(height: 24),
                Text(
                  pendingCount > 0 
                  ? '$pendingCount Pending Upload(s)' 
                  : 'All Data Synced',
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 16),
                Text(
                  pendingCount > 0 
                  ? 'These deliveries were completed offline and need to be synced to the main server when signal returns.' 
                  : 'Your device is fully synchronized with the dispatch center.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.grey, fontSize: 16),
                ),
                const Spacer(),
                if (pendingCount > 0) ...[
                  if (_isSyncing)
                    const CircularProgressIndicator()
                  else
                    ElevatedButton.icon(
                      onPressed: _manualSync,
                      icon: const Icon(Icons.sync),
                      label: const Text('FORCE SYNC NOW'),
                    ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}
