import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:login_demo/widgets/login_form.dart';
import 'package:login_demo/l10n/l10n.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

void main() {
  testWidgets('LoginForm basic rendering and validation', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          locale: Locale('ru'),
          localizationsDelegates: [
            AppLocalizationsDelegate(),
            GlobalMaterialLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
          ],
          supportedLocales: [Locale('en'), Locale('ru')],
          home: Scaffold(
            body: LoginForm(),
          ),
        ),
      ),
    );

    expect(find.text('Email'), findsNothing);
    expect(find.text('Пароль'), findsOneWidget);
    expect(find.text('Войти'), findsWidgets);

    // Submit without input
    await tester.tap(find.text('Войти'));
    await tester.pump();
    expect(find.text('Введите email'), findsOneWidget);
    expect(find.text('Введите пароль'), findsOneWidget);

    // Enter invalid email and too short password
    await tester.enterText(find.byType(TextFormField).at(0), 'invalid');
    await tester.enterText(find.byType(TextFormField).at(1), '12345');
    await tester.tap(find.text('Войти'));
    await tester.pump();
    expect(find.text('Некорректный email'), findsOneWidget);
    expect(find.textContaining('не менее 6'), findsOneWidget);

    // Enter valid data
    await tester.enterText(find.byType(TextFormField).at(0), 'test@example.com');
    await tester.enterText(find.byType(TextFormField).at(1), '123456');
    await tester.tap(find.text('Войти'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byType(SnackBar), findsOneWidget);
  });
}
