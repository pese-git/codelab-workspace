import 'package:flutter_test/flutter_test.dart';
import 'package:project_name/models/user.dart';

void main() {
  group('User', () {
    test('getFullName returns correct full name', () {
      final user = User(firstName: 'John', lastName: 'Doe', email: 'john.doe@email.com');
      expect(user.getFullName(), 'John Doe');
    });
  });
}
