import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:test_project/utils/user_utils.dart';

void main() {
  group('UserUtils.buildUserList', () {
    testWidgets('should display a list of user names', (WidgetTester tester) async {
      final users = ['Alice', 'Bob', 'Charlie'];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: UserUtils.buildUserList(users),
          ),
        ),
      );

      for (final user in users) {
        expect(find.text(user), findsOneWidget);
      }
      expect(find.byType(ListTile), findsNWidgets(users.length));
    });

    testWidgets('should show empty list when no users', (WidgetTester tester) async {
      final users = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: UserUtils.buildUserList(users),
          ),
        ),
      );

      expect(find.byType(ListTile), findsNothing);
    });
  });
}
