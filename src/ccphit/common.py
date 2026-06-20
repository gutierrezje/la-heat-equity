import yaml


def load_config() -> dict:
    with open("config.yml", "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)