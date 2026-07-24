import 'package:flutter/material.dart';
import '../../../core/design/mascot_system.dart';

/// Mascot Rendering Widget matching base_design.md Section 5
class RipMascotWidget extends StatelessWidget {
  final RipMascotPose pose;
  final double width;
  final double height;
  final BoxFit fit;

  const RipMascotWidget({
    super.key,
    required this.pose,
    this.width = 120.0,
    this.height = 120.0,
    this.fit = BoxFit.contain,
  });

  factory RipMascotWidget.fromState({
    Key? key,
    required String state,
    double width = 120.0,
    double height = 120.0,
    BoxFit fit = BoxFit.contain,
  }) {
    return RipMascotWidget(
      key: key,
      pose: RipMascotPose.fromState(state),
      width: width,
      height: height,
      fit: fit,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      pose.assetPath,
      width: width,
      height: height,
      fit: fit,
      errorBuilder: (context, error, stackTrace) {
        // Fallback placeholder if asset loading encounters issues
        return Container(
          width: width,
          height: height,
          decoration: const BoxDecoration(
            color: Color(0xFFEDE9FE),
            shape: BoxShape.circle,
          ),
          child: const Icon(
            Icons.smart_toy_rounded,
            color: Color(0xFF5F3ADD),
            size: 48,
          ),
        );
      },
    );
  }
}
