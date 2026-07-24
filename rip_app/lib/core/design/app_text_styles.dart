import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';

/// Canonical Typography System for RIP.
/// Ref: base_design.md Section 1 & 2
abstract final class AppTextStyles {
  /// Big numbers ($12.45, 2.4M, 12)
  static final statXl = GoogleFonts.inter(
    fontSize: 32,
    fontWeight: FontWeight.w700,
    height: 40 / 32,
    letterSpacing: -0.02 * 32,
    color: AppColors.textPrimary,
  );

  /// Screen titles
  static final headlineLg = GoogleFonts.inter(
    fontSize: 20,
    fontWeight: FontWeight.w600,
    height: 28 / 20,
    color: AppColors.textPrimary,
  );

  /// Card titles & modal headlines
  static final headlineMd = GoogleFonts.inter(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    height: 24 / 16,
    color: AppColors.textPrimary,
  );

  /// Standard body copy & list titles
  static final bodyMd = GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 20 / 14,
    color: AppColors.textPrimary,
  );

  /// Emphasized body text / button labels
  static final bodyMdBold = GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    height: 20 / 14,
    color: AppColors.textPrimary,
  );

  /// Secondary metadata, timestamps, file sizes
  static final bodySm = GoogleFonts.inter(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    height: 18 / 12,
    color: AppColors.textSecondary,
  );

  /// Muted helper text
  static final bodySmMuted = GoogleFonts.inter(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    height: 18 / 12,
    color: AppColors.textMuted,
  );

  /// Caption / Small label
  static final caption = GoogleFonts.inter(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
  );

  /// HIGH IMPACT / Status pill uppercase caps tags
  static final labelCaps = GoogleFonts.inter(
    fontSize: 10,
    fontWeight: FontWeight.w700,
    height: 12 / 10,
    letterSpacing: 0.05 * 10,
    color: AppColors.textPrimary,
  );

  /// Code / Terminal / Log monospace output
  static final codeSm = GoogleFonts.jetBrainsMono(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    height: 18 / 12,
    color: AppColors.codeTextDefault,
  );

  /// Monospace alias
  static final mono = codeSm;

  // Backward compatibility aliases
  static TextStyle get headingLg => headlineLg;
  static TextStyle get headingMd => headlineMd;
}
