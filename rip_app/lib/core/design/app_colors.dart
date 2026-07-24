import 'package:flutter/material.dart';

/// Canonical Design Tokens for RIP's visual design system.
/// Ref: base_design.md Section 1
abstract final class AppColors {
  // Brand
  static const primary = Color(0xFF5F3ADD);          // buttons, active nav, links, mascot body
  static const primaryDark = Color(0xFF5B3FE0);      // hover/pressed
  static const primaryContainer = Color(0xFF7857F8); // gradient end / lighter brand fill
  static const primaryLight = Color(0xFFEDE9FE);     // selected row bg, subtle chips
  static const onPrimaryContainer = Color(0xFFE0D7FA);

  static const gradient = LinearGradient(
    colors: [Color(0xFF8B7CF6), Color(0xFF6D4FE8)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  // Surface
  static const background = Color(0xFFFAFAFC);        // page/app shell background
  static const surface = Color(0xFFFFFFFF);           // cards, panels
  static const surfaceContainerHigh = Color(0xFFEBE4FF); // elevated purple-tinted surfaces
  static const border = Color(0xFFECEAF3);            // all card borders/dividers, 1px
  static const surfaceVariant = Color(0xFFF0F2F7);

  // Text
  static const textPrimary = Color(0xFF1B1730);      // headings, primary content, code
  static const textSecondary = Color(0xFF6B6580);    // meta, timestamps, labels, placeholder
  static const textMuted = Color(0xFF8C86A0);

  // Semantic (Status ONLY — never decorative)
  static const success = Color(0xFF22C55E);           // Connected, Running, Passed, Success
  static const warning = Color(0xFFF59E0B);           // Partial, install-in-progress, warnings
  static const danger = Color(0xFFEF4444);            // Failed, Error, High Impact, destructive
  static const error = Color(0xFFEF4444);             // Alias for danger
  static const info = Color(0xFF3B82F6);              // GitHub/secondary integration accents, tags

  // Dark code surfaces (terminal, console, code editor bg)
  static const codeBg = Color(0xFF1E1E2E);
  static const codeTextOutput = Color(0xFF22C55E);  // stdout success lines
  static const codeTextDefault = Color(0xFFE4E1EE);

  // Specific Category Accents
  static const iconWorkflow = Color(0xFF8B5CF6);
  static const iconMermaid = Color(0xFF06B6D4);
  static const iconDeps = Color(0xFF10B981);
  static const iconState = Color(0xFFD946EF);
  static const iconFiles = Color(0xFFF59E0B);
  static const iconImpact = Color(0xFFF97316);
}
