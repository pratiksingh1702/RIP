import 'package:flutter/material.dart';

abstract final class AppColors {
  // Brand Backgrounds
  static const background = Color(0xFF0D0D0D);
  static const surface = Color(0xFF161616);
  static const surfaceVariant = Color(0xFF1E1E1E);
  static const border = Color(0xFF2A2A2A);

  // Text Colors
  static const textPrimary = Color(0xFFFFFFFF);
  static const textSecondary = Color(0xFF9E9E9E);
  static const textMuted = Color(0xFF555555);

  // Brand Accents
  static const primary = Color(0xFF7C3AED); // Purple
  static const primaryContainer = Color(0xFF2E1B4E);
  static const onPrimaryContainer = Color(0xFFE0D7FA);

  // Status & Icons
  static const success = Color(0xFF22C55E); // Connected green
  static const warning = Color(0xFFF59E0B); // Amber
  static const error = Color(0xFFEF4444); // Red
  static const info = Color(0xFF3B82F6); // Blue

  // Specific Icon Colors
  static const iconWorkflow = Color(0xFF8B5CF6);  // Purple-ish
  static const iconMermaid = Color(0xFF06B6D4);   // Cyan
  static const iconDeps = Color(0xFF10B981);      // Green
  static const iconState = Color(0xFFD946EF);     // Magenta
  static const iconFiles = Color(0xFFF59E0B);     // Amber
  static const iconImpact = Color(0xFFF97316);    // Orange
}
