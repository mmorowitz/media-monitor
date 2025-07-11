from abc import ABC, abstractmethod

class BaseMediaClient(ABC):
    def __init__(self, config):
        """
        Initialize with common category/simple format handling.
        Subclasses should call super().__init__(config) and then set up their specific clients.
        """
        # Support both simple and categorized formats
        if "categories" in config:
            self.categories = config["categories"]
            self.items = []
            for category_items in self.categories.values():
                self.items.extend(category_items)
        else:
            self.categories = None
            self.items = self._get_items_from_config(config)

    @abstractmethod
    def _get_items_from_config(self, config):
        """Extract items list from config for simple format. Override in subclasses."""
        pass

    @abstractmethod
    def _fetch_items_for_source(self, item, since_datetime):
        """Fetch items from a specific source (subreddit/channel). Override in subclasses."""
        pass

    def _pre_fetch_optimization(self, items):
        """
        Optional optimization hook for batch operations before fetching items.
        Override in subclasses to implement batch fetching.
        """
        pass

    def get_new_items_since(self, since_datetime):
        """
        Retrieve new items since the given datetime.
        Returns a list of dicts with item info, including category if categorized.
        """
        new_items = []

        # Allow subclasses to optimize with batch operations
        self._pre_fetch_optimization(self.items)

        # Create a mapping from item to category if using categories
        item_to_category = {}
        if self.categories:
            for category, item_list in self.categories.items():
                for item in item_list:
                    item_to_category[item] = category

        for item in self.items:
            items_from_source = self._fetch_items_for_source(item, since_datetime)

            # Add category if using categorized format
            if self.categories:
                for item_data in items_from_source:
                    item_data["category"] = item_to_category.get(item, "uncategorized")

            new_items.extend(items_from_source)

        return new_items