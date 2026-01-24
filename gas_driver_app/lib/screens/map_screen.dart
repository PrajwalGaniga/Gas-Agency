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
  bool _isMapReady = false;
  late GoogleMapController _mapController;

  // UX Constants
  final Color kNavBlue = const Color(0xFF1976D2);
  final Color kDarkSurface = const Color(0xFF212121);
  final Color kSuccessGreen = const Color(0xFF00E676);

  @override
  void initState() {
    super.initState();
    _processDailyRoute();
  }

  // 🛡️ Safe Value Parser: Prevents 'String is not a subtype of double'
  double _val(dynamic v) => (v is double) ? v : double.tryParse(v.toString()) ?? 0.0;

  void _processDailyRoute() {
    Set<Marker> newMarkers = {};
    List<LatLng> journeyPath = [];

    // 1. Sort orders chronologically to draw the path
    List sortedOrders = List.from(widget.orders);
    sortedOrders.sort((a, b) {
      var timeA = a['created_at'] ?? "";
      var timeB = b['created_at'] ?? "";
      return timeA.compareTo(timeB);
    });

    // 2. Identify Current Active Job
    _inProgressOrder = widget.orders.firstWhere(
      (o) => o['status'] == 'IN_PROGRESS',
      orElse: () => null,
    );

    // 3. Loop through all orders to build Markers and the Path
    for (var o in sortedOrders) {
      if (o['verified_lat'] == null) continue;

      LatLng point = LatLng(_val(o['verified_lat']), _val(o['verified_lng']));
      String status = o['status'] ?? 'PENDING';
      
      // Add point to the journey line if it's already delivered or active
      if (status != 'PENDING') {
        journeyPath.add(point);
      }

      // Determine Marker Color
      double hue = BitmapDescriptor.hueOrange; // Pending
      if (status == 'DELIVERED') hue = BitmapDescriptor.hueGreen;
      if (status == 'IN_PROGRESS') hue = BitmapDescriptor.hueAzure;

      newMarkers.add(Marker(
        markerId: MarkerId(o['_id'].toString()),
        position: point,
        icon: BitmapDescriptor.defaultMarkerWithHue(hue),
        infoWindow: InfoWindow(
          title: o['customer_name'] ?? "Customer",
          snippet: "${o['address'] ?? ''} (${status.toLowerCase()})",
        ),
      ));
    }

    // 4. Add Driver's Current Location (The Car)
    LatLng driverPoint = LatLng(widget.currentPos.latitude, widget.currentPos.longitude);
    newMarkers.add(Marker(
      markerId: const MarkerId('driver_car'),
      position: driverPoint,
      icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueBlue),
      infoWindow: const InfoWindow(title: "Your Current Location"),
    ));

    setState(() {
      _markers = newMarkers;
      // 🗺️ Draw the blue path connecting deliveries
      _polylines = {
        Polyline(
          polylineId: const PolylineId("journey_trail"),
          points: journeyPath,
          color: kNavBlue.withOpacity(0.7),
          width: 5,
          jointType: JointType.round,
        )
      };
      _isMapReady = true;
    });
  }

  Future<void> _launchTurnByTurn(double lat, double lng) async {
    final Uri googleMapsUrl = Uri.parse("google.navigation:q=$lat,$lng&mode=d");
    if (await canLaunchUrl(googleMapsUrl)) {
      await launchUrl(googleMapsUrl);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: kDarkSurface,
        foregroundColor: Colors.white,
        title: const Text("WORK DAY MAP", style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => Navigator.pop(context)),
      ),
      body: Stack(
        children: [
          GoogleMap(
            initialCameraPosition: CameraPosition(
              target: LatLng(widget.currentPos.latitude, widget.currentPos.longitude), 
              zoom: 14,
            ),
            markers: _markers,
            polylines: _polylines,
            myLocationEnabled: false, // We use our custom blue marker instead
            mapType: MapType.normal,
            onMapCreated: (c) => _mapController = c,
            padding: const EdgeInsets.only(bottom: 120),
          ),

          // 🏁 HUD: Heads Up Display for Active Job
          if (_inProgressOrder != null)
            Positioned(
              top: 20, left: 15, right: 15,
              child: _buildNavigationCard(),
            ),

          // 📍 Center Button
          Positioned(
            right: 15, bottom: 20,
            child: FloatingActionButton(
              backgroundColor: Colors.white,
              child: const Icon(Icons.my_location, color: Colors.black),
              onPressed: () => _mapController.animateCamera(
                CameraUpdate.newLatLng(LatLng(widget.currentPos.latitude, widget.currentPos.longitude))
              ),
            ),
          )
        ],
      ),
    );
  }

  Widget _buildNavigationCard() {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(15),
        boxShadow: [BoxShadow(color: Colors.black26, blurRadius: 10)]
      ),
      child: Row(
        children: [
          const Icon(Icons.local_gas_station, color: Colors.blue, size: 30),
          const SizedBox(width: 15),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text("ACTIVE DELIVERY", style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.grey)),
                Text(_inProgressOrder!['customer_name'] ?? "Unknown", style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                Text(_inProgressOrder!['address'] ?? "No address", maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: Colors.black54)),
              ],
            ),
          ),
          IconButton(
            onPressed: () => _launchTurnByTurn(_val(_inProgressOrder!['verified_lat']), _val(_inProgressOrder!['verified_lng'])),
            icon: const Icon(Icons.navigation, color: Colors.blue, size: 35),
          )
        ],
      ),
    );
  }
}