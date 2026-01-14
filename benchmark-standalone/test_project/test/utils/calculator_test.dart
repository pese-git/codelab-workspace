import 'package:flutter_test/flutter_test.dart';
import 'package:test_project/utils/calculator.dart';

void main() {
  group('Calculator', () {
    late Calculator calc;

    setUp(() {
      calc = Calculator();
    });

    test('add returns correct sum', () {
      expect(calc.add(2, 3), 5);
      expect(calc.add(-1, 1), 0);
      expect(calc.add(0, 0), 0);
    });

    test('subtract returns correct difference', () {
      expect(calc.subtract(5, 3), 2);
      expect(calc.subtract(0, 1), -1);
      expect(calc.subtract(-1, -1), 0);
    });

    test('multiply returns correct product', () {
      expect(calc.multiply(4, 5), 20);
      expect(calc.multiply(0, 100), 0);
      expect(calc.multiply(-2, 3), -6);
    });

    test('divide returns correct quotient', () {
      expect(calc.divide(10, 2), 5.0);
      expect(calc.divide(9, 3), 3.0);
      expect(calc.divide(-6, 2), -3.0);
    });

    test('divide throws ArgumentError on division by zero', () {
      expect(() => calc.divide(5, 0), throwsArgumentError);
    });
  });
}
