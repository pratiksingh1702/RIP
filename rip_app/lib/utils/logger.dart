import 'dart:developer' as dev;
import 'package:flutter/foundation.dart';

/// A beautiful logger for the RIP Flutter app.
class RipLogger {
  static const String _reset = '\x1B[0m';
  static const String _red = '\x1B[31m';
  static const String _green = '\x1B[32m';
  static const String _yellow = '\x1B[33m';
  static const String _blue = '\x1B[34m';
  static const String _magenta = '\x1B[35m';
  static const String _cyan = '\x1B[36m';
  static const String _white = '\x1B[37m';

  static void info(String message, {String tag = 'INFO'}) {
    _log('$_blue$message$_reset', tag: tag, level: 800);
  }

  static void success(String message, {String tag = 'SUCCESS'}) {
    _log('$_green$message$_reset', tag: tag, level: 800);
  }

  static void warning(String message, {String tag = 'WARNING'}) {
    _log('$_yellow$message$_reset', tag: tag, level: 900);
  }

  static void error(String message, {String tag = 'ERROR', Object? error, StackTrace? stackTrace}) {
    _log('$_red$message$_reset', tag: tag, level: 1000, error: error, stackTrace: stackTrace);
  }

  static void apiRequest(String method, String url, {Map<String, dynamic>? headers, Map<String, dynamic>? queryParameters, dynamic data}) {
    final methodColor = _getMethodColor(method);
    _log(
      '$methodColor$method$_reset $_cyan$url$_reset',
      tag: 'API_REQ',
      level: 800,
    );
    if (kDebugMode) {
      if (headers != null && headers.isNotEmpty) {
        // ignore: avoid_print
        print('  $_magentaApiReqHeaders$_reset:');
        headers.forEach((key, value) {
          final isToken = key.toLowerCase() == 'authorization';
          final valueStr = isToken ? '$_yellow$value$_reset' : value.toString();
          // ignore: avoid_print
          print('    [dim]$key:[/] $valueStr');
        });
      }
      if (queryParameters != null && queryParameters.isNotEmpty) {
        // ignore: avoid_print
        print('  $_cyanApiReqParams$_reset: $queryParameters');
      }
      if (data != null) {
        // ignore: avoid_print
        print('  $_yellowApiReqPayload$_reset: $data');
      }
    }
  }

  static const String _magentaApiReqHeaders = '\x1B[35mHEADERS';
  static const String _cyanApiReqParams = '\x1B[36mPARAMS';
  static const String _yellowApiReqPayload = '\x1B[33mPAYLOAD';

  static void apiResponse(int? statusCode, String url, {dynamic data, Map<String, dynamic>? headers, Duration? duration}) {
    final statusColor = _getStatusColor(statusCode);
    final timeStr = duration != null ? ' (${duration.inMilliseconds}ms)' : '';
    _log(
      '$statusColor$statusCode$_reset $_cyan$url$_reset$timeStr',
      tag: 'API_RES',
      level: 800,
    );
    if (kDebugMode) {
      if (headers != null && headers.isNotEmpty) {
        // ignore: avoid_print
        print('  $_magentaApiReqHeaders$_reset (Response):');
        headers.forEach((key, value) {
          // ignore: avoid_print
          print('    [dim]$key:[/] $value');
        });
      }
      if (data != null) {
        // ignore: avoid_print
        print('  $_greenApiResData$_reset: $data');
      }
    }
  }

  static const String _greenApiResData = '\x1B[32mDATA';

  static void _log(String message, {required String tag, int level = 0, Object? error, StackTrace? stackTrace}) {
    dev.log(
      message,
      name: tag,
      level: level,
      error: error,
      stackTrace: stackTrace,
      time: DateTime.now(),
    );
    
    if (kDebugMode) {
      // ignore: avoid_print
      print('[$tag] $message');
    }
  }

  static String _getMethodColor(String method) {
    switch (method.toUpperCase()) {
      case 'GET': return _cyan;
      case 'POST': return _magenta;
      case 'PUT': return _blue;
      case 'DELETE': return _red;
      default: return _white;
    }
  }

  static String _getStatusColor(int? statusCode) {
    if (statusCode == null) return _white;
    if (statusCode >= 200 && statusCode < 300) return _green;
    if (statusCode >= 300 && statusCode < 400) return _yellow;
    return _red;
  }
}
