import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';

class MapScreen extends StatefulWidget {
  final List orders;
  final Position currentPos;
  const MapScreen({super.key, required this.orders, required this.currentPos});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  Set<Marker> _markers = {};
  Set<Polyline> _polylines = {};
  Map? _inProgressOrder;
  List _unverified = [];
  bool _isMapReady = false;
  late GoogleMapController _mapController;

  // UX Constants
  final Color kNavBlue = const Color(0xFF1976D2);
  final Color kDarkSurface = const Color(0xFF212121);

  @override
  void initState() {
    super.initState();
    _processRouteData();
  }

  double _val(dynamic v) => (v is double) ? v : double.tryParse(v.toString()) ?? 0.0;

  void _processRouteData() {
    // 1. Identify Active Order
    _inProgressOrder = widget.orders.firstWhere(
      (o) => o['status'] == 'IN_PROGRESS' && o['verified_lat'] != null,
      orElse: () => null,
    );

    // 2. Filter Lists
    List verified = widget.orders.where((o) => 
      o['verified_lat'] != null && o['_id'] != _inProgressOrder?['_id']
    ).toList();
    
    _unverified = widget.orders.where((o) => o['verified_lat'] == null).toList();

    // 3. Build Route Logic (Simplified Nearest Neighbor for demo)
    List<LatLng> polyPoints = [LatLng(widget.currentPos.latitude, widget.currentPos.longitude)];
    Set<Marker> newMarkers = {};

    // A. Add Active Order (High Priority Marker)
    if (_inProgressOrder != null) {
      LatLng ipLatLng = LatLng(_val(_inProgressOrder!['verified_lat']), _val(_inProgressOrder!['verified_lng']));
      polyPoints.add(ipLatLng);
      
      newMarkers.add(Marker(
        markerId: const MarkerId('active_target'),
        position: ipLatLng,
        // In production, use a custom BitmapDescriptor for a big Green/Red Pin
        icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueGreen), 
        zIndex: 10, // Force on top
        infoWindow: InfoWindow(title: "TARGET: ${_inProgressOrder!['customer_name']}"),
      ));
    }

    // B. Add Verified Orders (Low Priority Markers)
    for (var o in verified) {
      newMarkers.add(Marker(
        markerId: MarkerId(o['_id'].toString()),
        position: LatLng(_val(o['verified_lat']), _val(o['verified_lng'])),
        icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueAzure),
        alpha: 0.8, // Slightly faded to reduce noise
      ));
    }

    setState(() {
      _polylines = {
        Polyline(
          polylineId: const PolylineId("master_route"),
          points: polyPoints,
          color: kNavBlue,
          width: 6, // Thick line for visibility
          jointType: JointType.round,
          startCap: Cap.roundCap,
          endCap: Cap.roundCap,
        )
      };
      _markers = newMarkers;
      _isMapReady = true;
    });
  }

  Future<void> _launchTurnByTurn(double lat, double lng) async {
    final Uri googleMapsUrl = Uri.parse("google.navigation:q=$lat,$lng&mode=d");
    if (await canLaunchUrl(googleMapsUrl)) {
      await launchUrl(googleMapsUrl);
    } else {
      // Fallback
      await launchUrl(Uri.parse("https://www.google.com/maps/dir/?api=1&destination=$lat,$lng"));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // 🗺️ LAYER 1: CLEAN MAP
          GoogleMap(
            initialCameraPosition: CameraPosition(
              target: LatLng(widget.currentPos.latitude, widget.currentPos.longitude), 
              zoom: 15,
              tilt: 40 // Slight tilt for "Driver Perspective"
            ),
            markers: _markers,
            polylines: _polylines,
            myLocationEnabled: true,
            myLocationButtonEnabled: false, // We build our own custom button
            zoomControlsEnabled: false, // Remove clutter
            mapToolbarEnabled: false, // Remove clutter
            onMapCreated: (c) => _mapController = c,
            padding: const EdgeInsets.only(top: 140, bottom: 100), // Safe area for overlays
          ),

          // 🧭 LAYER 2: TOP NAVIGATION CARD (Active Order)
          if (_inProgressOrder != null)
             Positioned(
              top: 50, left: 16, right: 16,
              child: _buildTopNavCard(),
            ),

          // 📍 LAYER 3: RE-CENTER BUTTON
          Positioned(
            right: 16, bottom: 120, // Above the bottom sheet
            child: FloatingActionButton(
              backgroundColor: Colors.white,
              foregroundColor: Colors.black87,
              elevation: 4,
              child: const Icon(Icons.gps_fixed),
              onPressed: () {
                _mapController.animateCamera(
                  CameraUpdate.newLatLng(LatLng(widget.currentPos.latitude, widget.currentPos.longitude))
                );
              },
            ),
          ),

          // 📂 LAYER 4: BOTTOM SHEET (Unverified/Queue)
          DraggableScrollableSheet(
            initialChildSize: 0.1,
            minChildSize: 0.1,
            maxChildSize: 0.5,
            builder: (context, scrollController) {
              return Container(
                decoration: BoxDecoration(
                  color: kDarkSurface,
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                  boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.4), blurRadius: 10, offset: const Offset(0, -2))]
                ),
                child: ListView(
                  controller: scrollController,
                  padding: EdgeInsets.zero,
                  children: [
                    // Handle
                    Center(
                      child: Container(
                        margin: const EdgeInsets.symmetric(vertical: 12),
                        width: 40, height: 4,
                        decoration: BoxDecoration(color: Colors.grey[600], borderRadius: BorderRadius.circular(2)),
                      ),
                    ),
                    
                    // Header
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 5),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline, color: Colors.orangeAccent, size: 20),
                          const SizedBox(width: 10),
                          const Text("Unverified Address Queue", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                          const Spacer(),
                          Text("${_unverified.length}", style: const TextStyle(color: Colors.white54, fontWeight: FontWeight.bold)),
                        ],
                      ),
                    ),
                    const Divider(color: Colors.white10),
                    
                    // List
                    ..._unverified.map((o) => ListTile(
                      dense: true,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 20),
                      title: Text(o['customer_name'], style: const TextStyle(color: Colors.white70)),
                      subtitle: Text(o['address'], maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white30)),
                      trailing: const Icon(Icons.chevron_right, color: Colors.white24),
                    )),
                    // Spacer for scrolling
                    const SizedBox(height: 20),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  // 🚀 COMPONENT: The "Heads Up" Display
  Widget _buildTopNavCard() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.2), blurRadius: 15, offset: const Offset(0, 5))
        ]
      ),
      child: Column(
        children: [
          // Status Bar
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
            decoration: BoxDecoration(
              color: kNavBlue.withOpacity(0.1),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(16))
            ),
            child: Row(
              children: [
                Icon(Icons.flash_on, size: 14, color: kNavBlue),
                const SizedBox(width: 4),
                Text("CURRENT DESTINATION", style: TextStyle(color: kNavBlue, fontSize: 10, fontWeight: FontWeight.w900, letterSpacing: 1)),
                const Spacer(),
                Text("${(_inProgressOrder?['distance'] ?? 0).toStringAsFixed(1)} km away", style: const TextStyle(color: Colors.black54, fontSize: 11, fontWeight: FontWeight.bold)),
              ],
            ),
          ),
          
          // Main Info Area
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _inProgressOrder!['customer_name'].toString(), 
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Colors.black87)
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _inProgressOrder!['address'].toString(), 
                        style: const TextStyle(fontSize: 13, color: Colors.black54, height: 1.2),
                        maxLines: 2, 
                        overflow: TextOverflow.ellipsis
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                
                // 🧭 Big CTA Button
                SizedBox(
                  height: 50, width: 50,
                  child: FloatingActionButton(
                    onPressed: () => _launchTurnByTurn(
                      _val(_inProgressOrder!['verified_lat']), 
                      _val(_inProgressOrder!['verified_lng'])
                    ),
                    backgroundColor: kNavBlue,
                    elevation: 2,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    child: const Icon(Icons.navigation, size: 28, color: Colors.white),
                  ),
                )
              ],
            ),
          ),
        ],
      ),
    );
  }
}