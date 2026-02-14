"""Dataset loading utility for injection testing.

Loads samples from a HuggingFace dataset (default: AG News) and groups
them by class name, providing real article content for probe payloads.
"""

import random
from collections import defaultdict

AG_NEWS_LABEL_MAPPING = {1: "World", 2: "Sports", 3: "Business", 4: "SciTech"}


def load_dataset_samples(
    dataset_name: str = "sh0416/ag_news",
    split: str = "test",
    samples_per_class: int = 5,
    label_mapping: dict[int, str] | None = None,
    seed: int = 42,
) -> dict[str, list[str]]:
    """Load dataset samples grouped by class name.

    Args:
        dataset_name: HuggingFace dataset identifier.
        split: Dataset split to use.
        samples_per_class: Number of samples to return per class.
        label_mapping: Maps integer labels to class name strings.
            Defaults to AG News mapping.
        seed: Random seed for reproducible sampling.

    Returns:
        Dict mapping class name -> list of article text strings.
    """
    from datasets import load_dataset

    if label_mapping is None:
        label_mapping = AG_NEWS_LABEL_MAPPING

    dataset = load_dataset(dataset_name, split=split)

    # Group all articles by class
    by_class: dict[str, list[str]] = defaultdict(list)
    for item in dataset:
        label = item["label"]
        class_name = label_mapping.get(label)
        if class_name is None:
            continue
        text = f"{item['title']}: {item['description']}"
        by_class[class_name].append(text)

    # Shuffle and sample
    rng = random.Random(seed)
    result: dict[str, list[str]] = {}
    for class_name in sorted(by_class.keys()):
        articles = by_class[class_name]
        rng.shuffle(articles)
        result[class_name] = articles[:samples_per_class]

    return result
