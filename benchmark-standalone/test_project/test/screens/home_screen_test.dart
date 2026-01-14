import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:test_project/screens/home_screen.dart';

void main() {
  testWidgets('Counter increments when button is pressed', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: HomeScreen(),
      ),
    );

    expect(find.text('Counter: 0'), findsOneWidget);
    await tester.tap(find.byType(FloatingActionButton));
    await tester.pump();
    expect(find.text('Counter: 1'), findsOneWidget);
  });
}
