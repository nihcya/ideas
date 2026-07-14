/// 今日一点题目类型
typedef SparkType = String; // random_word | analogy | constraint | reverse_question

/// 今日一点题目响应
class SparkToday {
  final DateTime date;
  final String question;
  final String type;
  final int durationSeconds;
  final bool hasDraft;
  final bool submitted;

  const SparkToday({
    required this.date,
    required this.question,
    required this.type,
    required this.durationSeconds,
    required this.hasDraft,
    required this.submitted,
  });

  factory SparkToday.fromJson(Map<String, dynamic> json) {
    return SparkToday(
      date: DateTime.parse(json['date'] as String),
      question: json['question'] as String,
      type: json['type'] as String,
      durationSeconds: json['duration_seconds'] as int? ?? 180,
      hasDraft: json['has_draft'] as bool? ?? false,
      submitted: json['submitted'] as bool? ?? false,
    );
  }
}

/// 保存草稿响应
class SparkDraft {
  final bool saved;
  final DateTime expiresAt;
  final bool firstSave;

  const SparkDraft({
    required this.saved,
    required this.expiresAt,
    required this.firstSave,
  });

  factory SparkDraft.fromJson(Map<String, dynamic> json) {
    return SparkDraft(
      saved: json['saved'] as bool? ?? true,
      expiresAt: DateTime.parse(json['expires_at'] as String),
      firstSave: json['first_save'] as bool? ?? false,
    );
  }
}

/// 提交今日一点响应
class SparkSubmitResult {
  final String id;
  final String source;
  final String borderStyle;
  final String colorHex;

  const SparkSubmitResult({
    required this.id,
    required this.source,
    required this.borderStyle,
    required this.colorHex,
  });

  factory SparkSubmitResult.fromJson(Map<String, dynamic> json) {
    return SparkSubmitResult(
      id: json['id'] as String,
      source: json['source'] as String? ?? 'today_spark',
      borderStyle: json['border_style'] as String? ?? 'gold-thin',
      colorHex: json['color_hex'] as String,
    );
  }
}
