import 'package:flutter_test/flutter_test.dart';
import '../../lib/utils/calculator.dart';

void main() {
  late Calculator calculator;

  setUp(() {
    calculator = Calculator();
  });

  group('Calculator add', () {
    test('returns correct sum for positive numbers', () {
      expect(calculator.add(3, 2), 5);
    });
    test('returns correct sum with zero', () {
      expect(calculator.add(5, 0), 5);
    });
    test('returns correct sum for negative numbers', () {
      expect(calculator.add(-3, -2), -5);
    });
  });

  group('Calculator subtract', () {
    test('returns correct difference for positive numbers', () {
      expect(calculator.subtract(5, 3), 2);
    });
    test('returns correct difference with zero', () {
      expect(calculator.subtract(7, 0), 7);
    });
    test('returns correct difference for negative numbers', () {
      expect(calculator.subtract(-5, -2), -3);
    });
  });

  group('Calculator multiply', () {
    test('returns correct product for positive numbers', () {
      expect(calculator.multiply(4, 3), 12);
    });
    test('returns correct product with zero', () {
      expect(calculator.multiply(5, 0), 0);
    });
    test('returns correct product for negative numbers', () {
      expect(calculator.multiply(-4, 3), -12);
    });
  });

  group('Calculator divide', () {
    test('returns correct quotient for positive numbers', () {
      expect(calculator.divide(8, 2), 4);
    });
    test('returns correct quotient for negative numerator', () {
      expect(calculator.divide(-8, 2), -4);
    });
    test('returns correct quotient for negative denominator', () {
      expect(calculator.divide(8, -2), -4);
    });
    test('throws ArgumentError when dividing by zero', () {
      expect(() => calculator.divide(5, 0), throwsArgumentError);
    });
  });
}
