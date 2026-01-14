import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:test_project/screens/product_list_screen.dart';

void main() {
  group('ProductListScreen', () {
    testWidgets('filters products by search query with debounce', (WidgetTester tester) async {
      final products = [
        Product(name: 'Apple', price: 30.0),
        Product(name: 'Banana', price: 20.0),
        Product(name: 'Orange', price: 25.0),
        null,
      ];
      await tester.pumpWidget(
        MaterialApp(home: ProductListScreen(products: products)),
      );
      // All items including null
      expect(find.text('Apple'), findsOneWidget);
      expect(find.text('Banana'), findsOneWidget);
      expect(find.text('Orange'), findsOneWidget);
      expect(find.text('Нет данных'), findsOneWidget);

      // Search for 'Banana'
      await tester.enterText(find.byType(TextField), 'Ban');
      await tester.pump(const Duration(milliseconds: 200));
      expect(find.text('Banana'), findsOneWidget); // debounce, not filtered out yet
      await tester.pump(const Duration(milliseconds: 300));
      // Now only Banana remains
      expect(find.text('Banana'), findsOneWidget);
      expect(find.text('Apple'), findsNothing);
      expect(find.text('Orange'), findsNothing);

      // Clear search
      await tester.enterText(find.byType(TextField), '');
      await tester.pump(const Duration(milliseconds: 400));
      expect(find.text('Apple'), findsOneWidget);
      expect(find.text('Banana'), findsOneWidget);
      expect(find.text('Orange'), findsOneWidget);
      expect(find.text('Нет данных'), findsOneWidget);
    });
  });
}
