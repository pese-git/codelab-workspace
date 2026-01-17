import 'package:flutter_test/flutter_test.dart';
import 'package:test_project/utils/calculator.dart';

void main() {
  group('Calculator', () {
    final calculator = Calculator();

    test('add returns the sum of two numbers', () {
      expect(calculator.add(2, 3), 5);
      expect(calculator.add(-2, 3), 1);
      expect(calculator.add(0, 0), 0);
    });

    test('subtract returns the difference between two numbers', () {
      expect(calculator.subtract(5, 2), 3);
      expect(calculator.subtract(2, 5), -3);
      expect(calculator.subtract(0, 0), 0);
    });

    test('multiply returns the product of two numbers', () {
      expect(calculator.multiply(2, 3), 6);
      expect(calculator.multiply(-2, 3), -6);
      expect(calculator.multiply(0, 10), 0);
    });

    test('divide returns the quotient of two numbers as double', () {
      expect(calculator.divide(6, 3), 2.0);
      expect(calculator.divide(7, 2), 3.5);
    });

    test('divide throws ArgumentError when dividing by zero', () {
      expect(() => calculator.divide(3, 0), throwsA(isA<ArgumentError>()));
    });
  });
}
