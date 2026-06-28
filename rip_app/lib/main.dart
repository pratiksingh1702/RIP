import 'dart:developer';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';

void main() {
  log('[main] Starting app...', name: 'Main');
  runApp(
    const ProviderScope(
      child: App(),
    ),
  );
}
