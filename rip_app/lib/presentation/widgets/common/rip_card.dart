import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';

/// Canonical Card Component matching base_design.md Section 4
class RipCard extends StatefulWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final Color? backgroundColor;
  final BorderSide? borderSide;
  final double borderRadius;

  const RipCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.onTap,
    this.backgroundColor,
    this.borderSide,
    this.borderRadius = 12.0, // Standard card radius 12px
  });

  @override
  State<RipCard> createState() => _RipCardState();
}

class _RipCardState extends State<RipCard> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final effectiveBorderSide = widget.borderSide ?? const BorderSide(color: AppColors.border, width: 1);
    final effectiveBg = widget.backgroundColor ?? AppColors.surface;

    final boxDecoration = BoxDecoration(
      color: effectiveBg,
      borderRadius: BorderRadius.circular(widget.borderRadius),
      border: Border.fromBorderSide(effectiveBorderSide),
      boxShadow: (_isHovered && widget.onTap != null)
          ? [
              const BoxShadow(
                color: Color.fromRGBO(28, 24, 49, 0.06),
                blurRadius: 12,
                offset: Offset(0, 4),
              ),
            ]
          : null, // Flat at rest per base_design.md
    );

    Widget content = Container(
      padding: widget.padding,
      decoration: boxDecoration,
      child: widget.child,
    );

    if (widget.onTap != null) {
      return MouseRegion(
        onEnter: (_) => setState(() => _isHovered = true),
        onExit: (_) => setState(() => _isHovered = false),
        child: GestureDetector(
          onTap: widget.onTap,
          behavior: HitTestBehavior.opaque,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            child: content,
          ),
        ),
      );
    }

    return content;
  }
}
