class ProjectNotFoundError(ValueError):
    pass


class NoKnowledgeMatchedError(ValueError):
    pass


class AnalysisRunNotFoundError(ValueError):
    pass


class CodingResponseFormatError(ValueError):
    pass


class NoSavedCodingResultsError(ValueError):
    pass


LLM_CONFIG_ERROR_MESSAGE = "LLM 未配置，请设置环境变量后重试"
