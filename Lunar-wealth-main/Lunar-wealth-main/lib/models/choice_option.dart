class ChoiceOption {
  final String id;
  final String label;
  final String description;
  final Map<String, dynamic> consequences;
  final int resourceCost;

  const ChoiceOption({
    required this.id,
    required this.label,
    required this.description,
    required this.consequences,
    this.resourceCost = 0,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'label': label,
      'description': description,
      'consequences': consequences,
      'resourceCost': resourceCost,
    };
  }

  factory ChoiceOption.fromJson(Map<String, dynamic> json) {
    return ChoiceOption(
      id: json['id'] as String,
      label: json['label'] as String,
      description: json['description'] as String,
      consequences: json['consequences'] as Map<String, dynamic>,
      resourceCost: json['resourceCost'] as int? ?? 0,
    );
  }

  ChoiceOption copyWith({
    String? id,
    String? label,
    String? description,
    Map<String, dynamic>? consequences,
    int? resourceCost,
  }) {
    return ChoiceOption(
      id: id ?? this.id,
      label: label ?? this.label,
      description: description ?? this.description,
      consequences: consequences ?? this.consequences,
      resourceCost: resourceCost ?? this.resourceCost,
    );
  }
}
