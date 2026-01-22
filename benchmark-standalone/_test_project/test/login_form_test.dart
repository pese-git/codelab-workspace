import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:your_project/widgets/login_form.dart';

void main() {
  testWidgets('LoginForm basic validation', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: LoginForm()),
      ),
    );
    
    final emailField = find.byType(TextFormField).at(0);
    final passwordField = find.byType(TextFormField).at(1);
    final loginButton = find.text('Войти');

    // Initially, tap login and expect validation errors
    await tester.tap(loginButton);
    await tester.pump();
    expect(find.text('Введите email'), findsOneWidget);
    expect(find.text('Введите пароль'), findsOneWidget);

    // Invalid email
    await tester.enterText(emailField, 'not_an_email');
    await tester.enterText(passwordField, '12345');
    await tester.tap(loginButton);
    await tester.pump();
    expect(find.text('Некорректный email'), findsOneWidget);
    expect(find.text('Минимум 6 символов'), findsOneWidget);

    // Valid fields
    await tester.enterText(emailField, 'test@example.com');
    await tester.enterText(passwordField, '123456');
    await tester.tap(loginButton);
    await tester.pump();
    expect(find.text('Logging in...'), findsOneWidget);
  });
}
