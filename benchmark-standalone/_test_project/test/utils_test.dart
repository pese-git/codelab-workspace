import 'package:flutter_test/flutter_test.dart';
import 'package:login_demo/utils/utils.dart';

void main() {
  group('Utils.isValidEmail', () {
    test('valid email returns true', () {
      expect(Utils.isValidEmail('test@example.com'), isTrue);
      expect(Utils.isValidEmail('user@domain.co'), isTrue);
      expect(Utils.isValidEmail('user.name+tag+sorting@example.com'), isTrue);
      expect(Utils.isValidEmail('a@b.io'), isTrue);
    });
    test('invalid email returns false', () {
      expect(Utils.isValidEmail('testexample.com'), isFalse);
      expect(Utils.isValidEmail('user@domain'), isFalse);
      expect(Utils.isValidEmail('user@.com'), isFalse);
      expect(Utils.isValidEmail('user@com.'), isFalse);
      expect(Utils.isValidEmail('a@b'), isFalse);
      expect(Utils.isValidEmail(''), isFalse);
      expect(Utils.isValidEmail('test@ example.com'), isFalse);
      expect(Utils.isValidEmail(' test@example.com'), isFalse);
      expect(Utils.isValidEmail('test@ex ample.com'), isFalse);
    });
  });

  group('Utils.isValidPassword', () {
    test('valid password returns true', () {
      expect(Utils.isValidPassword('abc123'), isTrue);
      expect(Utils.isValidPassword('A1b2c3d4'), isTrue);
      expect(Utils.isValidPassword('passW0rd'), isTrue);
    });
    test('short password returns false', () {
      expect(Utils.isValidPassword('123'), isFalse);
      expect(Utils.isValidPassword(''), isFalse);
      expect(Utils.isValidPassword('abc'), isFalse);
    });
    test('password with only digits returns false', () {
      expect(Utils.isValidPassword('123456'), isFalse);
    });
    test('password with only letters returns false', () {
      expect(Utils.isValidPassword('abcdefg'), isFalse);
    });
    test('password containing spaces returns false', () {
      expect(Utils.isValidPassword('abc 123'), isFalse);
      expect(Utils.isValidPassword(' abcd1'), isFalse);
      expect(Utils.isValidPassword('abcd1 '), isFalse);
    });
    test('minLength argument works', () {
      expect(Utils.isValidPassword('abc123', minLength: 8), isFalse);
      expect(Utils.isValidPassword('abcd1234', minLength: 8), isTrue);
      expect(Utils.isValidPassword('ab12cd34ef', minLength: 8), isTrue);
    });
  });
}
