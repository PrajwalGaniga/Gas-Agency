import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';

class MapScreen extends StatelessWidget {
  final List orders;
  final Position currentPos;
  const MapScreen({super.key, required this.orders, required this.currentPos});

  // 🛡️ Helper to safely convert dynamic types to double
  double _convertToDouble(dynamic value) {
    if (value is double) return value;
    if (value is String) return double.tryParse(value) ?? 0.0;
    return 0.0;
  }

  @override
  Widget build(BuildContext context) {
    // Generate markers only for customers with verified GPS
    Set<Marker> markers = orders
        .where((o) => o['verified_lat'] != null && o['verified_lng'] != null)
        .map((o) {
      return Marker(
        markerId: MarkerId(o['_id'].toString()),
        position: LatLng(
          _convertToDouble(o['verified_lat']), // 🚀 FIX: Handles double or String
          _convertToDouble(o['verified_lng']), // 🚀 FIX: Handles double or String
        ),
        infoWindow: InfoWindow(
          title: o['customer_name'],
          snippet: o['address'],
        ),
        icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueAzure),
      );
    }).toSet();

    return Scaffold(
      appBar: AppBar(
        title: const Text("Delivery Route Map"),
        backgroundColor: const Color(0xFF0D47A1),
        foregroundColor: Colors.white,
      ),
      body: Stack(
        children: [
          GoogleMap(
            initialCameraPosition: CameraPosition(
                target: LatLng(currentPos.latitude, currentPos.longitude),
                zoom: 12),
            markers: markers,
            myLocationEnabled: true,
            myLocationButtonEnabled: true,
            mapType: MapType.normal,
          ),
          
          // Floating List Summary for the driver
          Positioned(
            bottom: 20,
            left: 10,
            right: 10,
            child: SizedBox(
              height: 100,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: orders.length,
                itemBuilder: (context, index) {
                  final o = orders[index];
                  return Card(
                    margin: const EdgeInsets.symmetric(horizontal: 5),
                    child: Container(
                      width: 200,
                      padding: const EdgeInsets.all(10),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(o['customer_name'], style: const TextStyle(fontWeight: FontWeight.bold)),
                          Text(o['address'], style: const TextStyle(fontSize: 11, color: Colors.grey), maxLines: 2),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}