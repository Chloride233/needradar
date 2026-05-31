
from needradar.schemas.schemas import ExtractedRequirement, SentimentEnum


def test_extracted_requirement_schema():
    req = ExtractedRequirement(
        title="AI PPT generator",
        description="Users want AI to create slides",
        sentiment=SentimentEnum.STRONG,
        use_case="Business presentations",
        pain_point="Manual slide creation is time-consuming",
    )
    assert req.title == "AI PPT generator"
    assert req.sentiment == SentimentEnum.STRONG


def test_extracted_requirement_default_sentiment():
    req = ExtractedRequirement(title="Test", description="Desc")
    assert req.sentiment == SentimentEnum.MODERATE
    assert req.use_case == ""


def test_extracted_requirement_from_json():
    json_str = '{"title": "AI Writing", "description": "Need AI writing tool", "sentiment": "strong"}'
    req = ExtractedRequirement.model_validate_json(json_str)
    assert req.sentiment == SentimentEnum.STRONG
