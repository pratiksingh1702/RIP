import 'dart:ui';
import 'package:flutter/material.dart';
import 'app_colors.dart';
import 'app_text_styles.dart';

class ChatChromeTheme extends ThemeExtension<ChatChromeTheme> {
  const ChatChromeTheme({
    required this.fadeColor,
    required this.composerSurface,
    required this.controlSurface,
    required this.suggestionSurface,
    required this.borderColor,
    required this.focusBorderColor,
    required this.shadowColor,
    required this.composerRadius,
    required this.composerExpandedRadius,
    required this.bottomFadeHeight,
  });

  const ChatChromeTheme.light()
      : fadeColor = AppColors.background,
        composerSurface = AppColors.surface,
        controlSurface = const Color(0xFFF0F2F7),
        suggestionSurface = AppColors.primaryLight,
        borderColor = AppColors.border,
        focusBorderColor = AppColors.primary,
        shadowColor = const Color(0x0F1C1831),
        composerRadius = 28,
        composerExpandedRadius = 26,
        bottomFadeHeight = 190;

  const ChatChromeTheme.dark()
      : fadeColor = AppColors.codeBg,
        composerSurface = AppColors.surface,
        controlSurface = AppColors.surfaceVariant,
        suggestionSurface = AppColors.primaryContainer,
        borderColor = AppColors.border,
        focusBorderColor = AppColors.primary,
        shadowColor = Colors.black,
        composerRadius = 28,
        composerExpandedRadius = 26,
        bottomFadeHeight = 190;

  final Color fadeColor;
  final Color composerSurface;
  final Color controlSurface;
  final Color suggestionSurface;
  final Color borderColor;
  final Color focusBorderColor;
  final Color shadowColor;
  final double composerRadius;
  final double composerExpandedRadius;
  final double bottomFadeHeight;

  @override
  ChatChromeTheme copyWith({
    Color? fadeColor,
    Color? composerSurface,
    Color? controlSurface,
    Color? suggestionSurface,
    Color? borderColor,
    Color? focusBorderColor,
    Color? shadowColor,
    double? composerRadius,
    double? composerExpandedRadius,
    double? bottomFadeHeight,
  }) {
    return ChatChromeTheme(
      fadeColor: fadeColor ?? this.fadeColor,
      composerSurface: composerSurface ?? this.composerSurface,
      controlSurface: controlSurface ?? this.controlSurface,
      suggestionSurface: suggestionSurface ?? this.suggestionSurface,
      borderColor: borderColor ?? this.borderColor,
      focusBorderColor: focusBorderColor ?? this.focusBorderColor,
      shadowColor: shadowColor ?? this.shadowColor,
      composerRadius: composerRadius ?? this.composerRadius,
      composerExpandedRadius: composerExpandedRadius ?? this.composerExpandedRadius,
      bottomFadeHeight: bottomFadeHeight ?? this.bottomFadeHeight,
    );
  }

  @override
  ChatChromeTheme lerp(ThemeExtension<ChatChromeTheme>? other, double t) {
    if (other is! ChatChromeTheme) return this;
    return ChatChromeTheme(
      fadeColor: Color.lerp(fadeColor, other.fadeColor, t)!,
      composerSurface: Color.lerp(composerSurface, other.composerSurface, t)!,
      controlSurface: Color.lerp(controlSurface, other.controlSurface, t)!,
      suggestionSurface: Color.lerp(suggestionSurface, other.suggestionSurface, t)!,
      borderColor: Color.lerp(borderColor, other.borderColor, t)!,
      focusBorderColor: Color.lerp(focusBorderColor, other.focusBorderColor, t)!,
      shadowColor: Color.lerp(shadowColor, other.shadowColor, t)!,
      composerRadius: lerpDouble(composerRadius, other.composerRadius, t)!,
      composerExpandedRadius:
          lerpDouble(composerExpandedRadius, other.composerExpandedRadius, t)!,
      bottomFadeHeight: lerpDouble(bottomFadeHeight, other.bottomFadeHeight, t)!,
    );
  }
}

abstract final class AppTheme {
  /// Canonical Light Theme matching base_design.md
  static ThemeData get ripLightTheme {
    final lightBase = ThemeData(brightness: Brightness.light);
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppColors.background, // #FAFAFC
      colorScheme: const ColorScheme.light(
        primary: AppColors.primary, // #5F3ADD
        onPrimary: Colors.white,
        primaryContainer: AppColors.primaryLight,
        onPrimaryContainer: AppColors.primaryDark,
        surface: AppColors.surface, // #FFFFFF
        onSurface: AppColors.textPrimary, // #1B1730
        onSurfaceVariant: AppColors.textSecondary, // #6B6580
        outline: AppColors.border, // #ECEAF3
        error: AppColors.danger, // #EF4444
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.background,
        elevation: 0,
        centerTitle: false,
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        titleTextStyle: AppTextStyles.headlineLg,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        hintStyle: AppTextStyles.bodySm,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.surface,
        selectedColor: AppColors.primaryLight,
        disabledColor: AppColors.surfaceVariant,
        labelStyle: AppTextStyles.bodySm.copyWith(color: AppColors.textPrimary),
        secondaryLabelStyle: AppTextStyles.bodySm.copyWith(color: AppColors.textPrimary),
        side: const BorderSide(color: AppColors.border),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9999)),
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface, // White bg
        elevation: 0, // Flat at rest per base_design.md
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12), // 12px radius
          side: const BorderSide(color: AppColors.border), // 1px #ECEAF3 border
        ),
      ),
      iconTheme: const IconThemeData(color: AppColors.textPrimary),
      textTheme: lightBase.textTheme.apply(
        bodyColor: AppColors.textPrimary,
        displayColor: AppColors.textPrimary,
      ),
      extensions: const <ThemeExtension<dynamic>>[
        ChatChromeTheme.light(),
      ],
    );
  }

  /// Canonical Dark Theme (for Code/Terminal surfaces or dark preference)
  static ThemeData get ripDarkTheme {
    final darkBase = ThemeData(brightness: Brightness.dark);
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.codeBg,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.primary,
        onPrimary: Colors.white,
        primaryContainer: AppColors.primaryContainer,
        onPrimaryContainer: AppColors.onPrimaryContainer,
        surface: AppColors.surface,
        onSurface: AppColors.textPrimary,
        onSurfaceVariant: AppColors.textSecondary,
        outline: AppColors.border,
        error: AppColors.danger,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.codeBg,
        elevation: 0,
        centerTitle: false,
        iconTheme: const IconThemeData(color: Colors.white),
        titleTextStyle: AppTextStyles.headlineLg.copyWith(color: Colors.white),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surfaceVariant,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        hintStyle: AppTextStyles.bodySm,
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AppColors.border),
        ),
      ),
      iconTheme: const IconThemeData(color: AppColors.textPrimary),
      textTheme: darkBase.textTheme.apply(
        bodyColor: AppColors.textPrimary,
        displayColor: AppColors.textPrimary,
      ),
      extensions: const <ThemeExtension<dynamic>>[
        ChatChromeTheme.dark(),
      ],
    );
  }

  // Alias for backward compatibility
  static ThemeData get lightTheme => ripLightTheme;
  static ThemeData get darkTheme => ripDarkTheme;
}
