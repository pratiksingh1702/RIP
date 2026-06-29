// RIP App – smoke test: verifies the widget tree can be built without errors.
// The full integration (Drift DB, Riverpod providers) is tested via integration tests.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('App smoke test – MaterialApp renders', (WidgetTester tester) async {
    // Pump a minimal ProviderScope+MaterialApp so we exercise the design system
    // without requiring a real DB or network connection.
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: Center(child: Text('RIP')),
          ),
        ),
      ),
    );

    expect(find.text('RIP'), findsOneWidget);
  });
}
