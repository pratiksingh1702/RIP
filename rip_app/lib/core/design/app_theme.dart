import 'dart:ui';

import 'package:flutter/material.dart';
import 'app_colors.dart';

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

  const ChatChromeTheme.dark()
      : fadeColor = AppColors.background,
        composerSurface = AppColors.surface,
        controlSurface = AppColors.surface,
        suggestionSurface = AppColors.surfaceVariant,
        borderColor = AppColors.border,
        focusBorderColor = AppColors.primary,
        shadowColor = Colors.black,
        composerRadius = 28,
        composerExpandedRadius = 26,
        bottomFadeHeight = 190;

  const ChatChromeTheme.light()
      : fadeColor = const Color(0xFFF6F7FB),
        composerSurface = Colors.white,
        controlSurface = const Color(0xFFE8EBF2),
        suggestionSurface = const Color(0xFFF0F2F7),
        borderColor = const Color(0xFFD6DAE3),
        focusBorderColor = AppColors.primary,
        shadowColor = const Color(0xFF64748B),
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
  static ThemeData get ripLightTheme {
    final lightBase = ThemeData(brightness: Brightness.light);
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: const Color(0xFFF6F7FB),
      colorScheme: const ColorScheme.light(
        primary: AppColors.primary,
        onPrimary: Colors.white,
        primaryContainer: Color(0xFFE9DDFF),
        onPrimaryContainer: Color(0xFF2E1065),
        surface: Colors.white,
        onSurface: Color(0xFF111827),
        onSurfaceVariant: Color(0xFF5B6472),
        outline: Color(0xFFD6DAE3),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFFF6F7FB),
        elevation: 0,
        centerTitle: false,
        iconTheme: IconThemeData(color: Color(0xFF111827)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFFF0F2F7),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(26),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(26),
          borderSide: BorderSide(color: AppColors.primary.withValues(alpha: 0.46)),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        hintStyle: const TextStyle(color: Color(0xFF5B6472), fontSize: 14),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: Colors.white,
        selectedColor: const Color(0xFFE9DDFF),
        disabledColor: const Color(0xFFF0F2F7),
        labelStyle: const TextStyle(color: Color(0xFF111827), fontSize: 12),
        secondaryLabelStyle: const TextStyle(color: Color(0xFF111827), fontSize: 12),
        side: const BorderSide(color: Color(0xFFD6DAE3)),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 8,
        shadowColor: const Color(0xFF64748B).withValues(alpha: 0.18),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(22),
          side: const BorderSide(color: Color(0xFFD6DAE3)),
        ),
      ),
      iconTheme: const IconThemeData(color: Color(0xFF111827)),
      textTheme: lightBase.textTheme.apply(
        bodyColor: const Color(0xFF111827),
        displayColor: const Color(0xFF111827),
      ),
      extensions: const <ThemeExtension<dynamic>>[
        ChatChromeTheme.light(),
      ],
    );
  }

  static ThemeData get ripDarkTheme {
    final darkBase = ThemeData(brightness: Brightness.dark);
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.background,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.primary,
        onPrimary: Colors.white,
        primaryContainer: AppColors.primaryContainer,
        onPrimaryContainer: AppColors.onPrimaryContainer,
        surface: AppColors.surface,
        onSurface: AppColors.textPrimary,
        onSurfaceVariant: AppColors.textSecondary,
        outline: AppColors.border,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.background,
        elevation: 0,
        centerTitle: false,
        iconTheme: IconThemeData(color: Colors.white),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surfaceVariant,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(26),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(26),
          borderSide: BorderSide(color: AppColors.primary.withValues(alpha: 0.42)),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        hintStyle: const TextStyle(color: AppColors.textSecondary, fontSize: 14),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.surface,
        selectedColor: AppColors.primaryContainer,
        disabledColor: AppColors.surface,
        labelStyle: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
        secondaryLabelStyle: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
        side: const BorderSide(color: AppColors.border),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface,
        elevation: 10,
        shadowColor: Colors.black.withValues(alpha: 0.28),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(22),
          side: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
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
}
