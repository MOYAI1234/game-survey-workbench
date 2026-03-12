METADATA_NAMES = {"标记", "时间戳记"}


def classify_column(column_name: str) -> str:
    if column_name in METADATA_NAMES:
        return "metadata"
    return "question"
