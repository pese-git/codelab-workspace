import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:test_project/widgets/user_card.dart';

dynamic testAssetImageProvider = const AssetImage('assets/avatar_placeholder.png');

void main() {
  testWidgets('UserCard displays name and avatar', (WidgetTester tester) async {
    const testName = 'John Doe';
    // Use blank avatar to force fallback to asset image
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: UserCard(
            name: testName,
            avatar: '',
          ),
        ),
      ),
    );
    expect(find.text(testName), findsOneWidget);
    expect(find.byType(CircleAvatar), findsOneWidget);
    final CircleAvatar avatar = tester.widget(find.byType(CircleAvatar));
    // Should fallback to AssetImage
    expect(avatar.backgroundImage, testAssetImageProvider);
  });
}
