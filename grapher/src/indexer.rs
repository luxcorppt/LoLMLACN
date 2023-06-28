use std::collections::BTreeMap;

pub struct Indexer {
    map: BTreeMap<String, i32>,
    next_id: i32
}

impl Indexer {
    pub fn new() -> Self {
        Indexer {
            map: BTreeMap::new(),
            next_id: 0
        }
    }

    pub fn insert_get(&mut self, item: String) -> i32 {
        if let Some(id) = self.map.get(&item) {
            return *id;
        }
        self.map.insert(item, self.next_id);
        let res = self.next_id;
        self.next_id += 1;
        return res;
    }

    pub fn into_map(self) -> BTreeMap<String, i32> {
        self.map
    }

    pub fn node_count(&self) -> usize {
        self.map.len()
    }
}