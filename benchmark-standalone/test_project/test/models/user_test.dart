import 'package:flutter_test/flutter_test.dart';
import 'package:test_project/models/user.dart';

void main() {
  group('User', () {
    test('getFullName returns correct full name', () {
      final user = User(firstName: 'John', lastName: 'Doe', email: 'john.doe@example.com');
      expect(user.getFullName(), 'John Doe');
    });
  });
}
