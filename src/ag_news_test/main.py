from pathlib import Path

from datasets import load_dataset
from src.folder_organizer.classifier import AIFileClassifier, ClassesDefinition, AppConfig
from src.folder_organizer.prompts import DirectPromptStrategy



def main():
    classes_definition = ClassesDefinition.from_yaml(Path("classes.yaml"))
    app_config = AppConfig.from_yaml(Path("app_config.yaml"))
    classifier = AIFileClassifier(classes_definition=classes_definition, app_config=app_config,
                                           prompt_strategy=DirectPromptStrategy())
    dataset = load_dataset("sh0416/ag_news", split="test")
    for item in dataset:
        text = f"{item["title"]}: {item["description"]}"
        label = item["label"]
        prediction = classifier.classify(text)
        print(f"Text: {text}\nTrue Label: {label}\nPredicted Label: {prediction}\n{'-'*50}")


if __name__ == "__main__":
    ds = load_dataset("sh0416/ag_news", split="test")
    item = ds[0]
    print(ds[0])