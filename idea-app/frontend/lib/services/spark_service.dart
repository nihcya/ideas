import 'package:dio/dio.dart';

import '../models/spark.dart';
import 'api_client.dart';

/// 今日一点服务：获取题目 / 保存草稿 / 提交
class SparkService {
  final Dio _dio;

  SparkService(this._dio);

  /// 获取今日题目
  Future<SparkToday> getToday() async {
    try {
      final res = await _dio.get('/spark/today');
      return SparkToday.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 保存草稿（自动触发或手动触发）
  Future<SparkDraft> saveDraft(String content) async {
    try {
      final res = await _dio.post('/spark/draft', data: {
        'content': content,
      });
      return SparkDraft.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 提交今日一点入库
  Future<SparkSubmitResult> submit(String content) async {
    try {
      final res = await _dio.post('/spark/submit', data: {
        'content': content,
      });
      return SparkSubmitResult.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
}
