"""Pool of 1000 short, memorable, human-like nicknames (max 5 chars)."""

NICKNAMES = [
    # A
    "Ace", "Ada", "Aero", "Agave", "Ajax", "Aki", "Alba", "Alder", "Alex",
    "Alfa", "Ali", "Align", "Alloy", "Alpha", "Alto", "Amber", "Amigo",
    "Amos", "Amy", "Anchor", "Angel", "Anik", "Anna", "Ant", "Anvil",
    "April", "Aqua", "Ara", "Arch", "Arden", "Aria", "Ariel", "Ark", "Arno",
    "Arrow", "Art", "Ash", "Aspen", "Astro", "Atlas", "Atom", "Aura", "Avery",
    "Axel", "Axis", "Ayla", "Azure",
    # B
    "Bach", "Badge", "Baker", "Bale", "Banks", "Baron", "Basil", "Bay", "Bea",
    "Bean", "Bear", "Beat", "Beck", "Bell", "Benny", "Berg", "Berry", "Beth",
    "Birch", "Bird", "Blade", "Blair", "Blake", "Blaze", "Bliss", "Block",
    "Bloom", "Blue", "Bo", "Bolt", "Bond", "Bones", "Boo", "Boots", "Boris",
    "Bravo", "Brave", "Bree", "Brett", "Brick", "Brio", "Brook", "Bruno",
    "Buck", "Buddy", "Burn", "Burst", "Buzz",
    # C
    "Cade", "Cal", "Cap", "Carl", "Casey", "Cedar", "Cello", "Chad", "Chai",
    "Chase", "Chess", "Chief", "Chip", "Chris", "Chuck", "Cindy", "Cisco",
    "Clara", "Clark", "Clay", "Cleo", "Click", "Cliff", "Clint", "Clive",
    "Cloud", "Clyde", "Coal", "Cobra", "Cocoa", "Coco", "Cody", "Cole",
    "Comet", "Coral", "Cora", "Cork", "Cosmo", "Craig", "Crane", "Creek",
    "Crew", "Cross", "Crown", "Cruz", "Cubby", "Curry", "Cyber",
    # D
    "Dace", "Daffy", "Dagger", "Daisy", "Dale", "Dana", "Dane", "Danny",
    "Dare", "Dario", "Dart", "Dash", "Dawn", "Dean", "Decoy", "Delta",
    "Denim", "Derek", "Devin", "Dewy", "Dice", "Diego", "Digit", "Dina",
    "Dingo", "Dion", "Disco", "Diva", "Dizzy", "Dock", "Dodge", "Dolly",
    "Donna", "Donut", "Doom", "Dory", "Dove", "Drake", "Dream", "Drew",
    "Drift", "Duke", "Dune", "Dusty", "Dylan",
    # E
    "Eagle", "Earl", "Earth", "Echo", "Eddie", "Eden", "Edge", "Edith",
    "Edy", "Elan", "Elder", "Elena", "Eli", "Eliot", "Ella", "Ellis",
    "Elm", "Ember", "Emily", "Emma", "Enzo", "Epic", "Eric", "Ernie",
    "Ethan", "Eva", "Eve", "Evie", "Exile",
    # F
    "Fable", "Faith", "Fang", "Fanny", "Fawn", "Fay", "Felix", "Fern",
    "Fidel", "Fig", "Finch", "Finn", "Fiona", "Fire", "Fizz", "Flame",
    "Flash", "Fleet", "Fling", "Flint", "Flip", "Flora", "Floyd", "Flute",
    "Flynn", "Focus", "Fog", "Forge", "Fox", "Frank", "Fred", "Freya",
    "Fritz", "Frost", "Fudge", "Fury",
    # G
    "Gabe", "Gaia", "Gale", "Gamma", "Gary", "Gauge", "Gem", "Gene",
    "Ghost", "Giddy", "Gigi", "Gina", "Glen", "Glow", "Goat", "Goldie",
    "Grace", "Grant", "Grape", "Gray", "Green", "Greg", "Greta", "Grid",
    "Grim", "Grip", "Grizzly", "Grove", "Guard", "Guide", "Gus", "Gypsy",
    # H
    "Hack", "Halo", "Hana", "Hank", "Happy", "Hardy", "Harp", "Harry",
    "Haven", "Hawk", "Hazel", "Heart", "Heath", "Heidi", "Helen", "Henry",
    "Herb", "Hero", "Hilda", "Holly", "Homer", "Honey", "Honor", "Hope",
    "Horn", "Hugo", "Hulk", "Hyde",
    # I
    "Ice", "Ida", "Igor", "Inca", "India", "Indie", "Ingot", "Ink",
    "Iris", "Iron", "Isaac", "Isla", "Ivan", "Ivory", "Ivy",
    # J
    "Jace", "Jack", "Jade", "Jake", "James", "Jane", "Jarvis", "Jasper",
    "Jay", "Jazz", "Jean", "Jenny", "Jerry", "Jesse", "Jewel", "Jill",
    "Jimmy", "Joan", "Joel", "Joey", "John", "Joker", "Jolly", "Jonas",
    "Jones", "Joy", "Juan", "Judge", "Jules", "July", "June", "Juno",
    # K
    "Kai", "Kane", "Kara", "Karl", "Karma", "Kate", "Kay", "Keen",
    "Kelly", "Ken", "Kerry", "Kevin", "Khan", "King", "Kirk", "Kit",
    "Kite", "Kiwi", "Klaus", "Knox", "Koda", "Kurt", "Kyle",
    # L
    "Lace", "Lake", "Lana", "Lance", "Lane", "Larry", "Lars", "Laura",
    "Lava", "Leaf", "Leah", "Leon", "Leo", "Levi", "Lewis", "Lily",
    "Linda", "Link", "Lisa", "Lloyd", "Lock", "Loft", "Logan", "Loki",
    "Lora", "Lotus", "Louis", "Lucia", "Lucky", "Lucy", "Luke", "Luna",
    "Lux", "Lydia", "Lynch", "Lynn", "Lyric",
    # M
    "Mac", "Macy", "Mage", "Magic", "Magma", "Major", "Mako", "Mango",
    "Manor", "Maple", "Marco", "Maria", "Mark", "Mars", "Mason", "Match",
    "Maude", "Mavis", "Max", "Maya", "Maze", "Medal", "Mel", "Melody",
    "Mercy", "Mesa", "Metal", "Metro", "Mia", "Micro", "Miles", "Milo",
    "Mimi", "Mint", "Mira", "Misty", "Mitch", "Mocha", "Mojo", "Molly",
    "Moon", "Moose", "Morph", "Morse", "Moss", "Motor", "Mouse", "Moxie",
    "Mulan", "Muse", "Mylar",
    # N
    "Nadia", "Nail", "Nancy", "Nao", "Nash", "Navy", "Nelly", "Nemo",
    "Neo", "Nero", "Nest", "Neve", "Newt", "Nia", "Nick", "Nikki",
    "Ninja", "Nix", "Noah", "Noble", "Noel", "Nola", "Noon", "Nora",
    "Norse", "North", "Nova", "Nugget",
    # O
    "Oak", "Oasis", "Obi", "Ocean", "Odin", "Olive", "Ollie", "Olly",
    "Omar", "Omega", "Onyx", "Opal", "Orbit", "Oreo", "Orion", "Oscar",
    "Otis", "Otto", "Owen", "Owl", "Oxide",
    # P
    "Pablo", "Pace", "Paddy", "Page", "Paint", "Panda", "Panel", "Paris",
    "Park", "Patch", "Pax", "Peace", "Pearl", "Pedro", "Penny", "Peony",
    "Pepper", "Percy", "Perry", "Peter", "Petra", "Phase", "Phil", "Phoebe",
    "Piano", "Pilot", "Pine", "Ping", "Pip", "Pivot", "Pixel", "Pizza",
    "Plaid", "Plato", "Plum", "Pluto", "Poet", "Point", "Polka", "Polo",
    "Poppy", "Power", "Pride", "Prime", "Prism", "Prize", "Proof", "Proto",
    "Proxy", "Pulse", "Punch", "Punk", "Pyro",
    # Q
    "Quake", "Queen", "Quest", "Quick", "Quin", "Quinn", "Quirk", "Quiz",
    # R
    "Radar", "Rafe", "Rain", "Raja", "Rally", "Ralph", "Rami", "Raven",
    "Ray", "Rebel", "Reed", "Reef", "Rex", "Rhino", "Rico", "Ridge",
    "Riley", "Rio", "Riser", "River", "Robin", "Rocky", "Roger", "Rogue",
    "Roman", "Ronin", "Rory", "Rosa", "Rose", "Rowan", "Roy", "Ruby",
    "Rue", "Rufus", "Rush", "Rust", "Ruth", "Ryan",
    # S
    "Saber", "Sadie", "Sage", "Salem", "Sally", "Sam", "Sandy", "Santa",
    "Sara", "Sasha", "Satin", "Scale", "Scout", "Seal", "Sean", "Seren",
    "Seth", "Seven", "Shade", "Shane", "Sharp", "Shaw", "Shell", "Shift",
    "Shiny", "Shock", "Sigma", "Silva", "Simon", "Siren", "Sky", "Slate",
    "Slim", "Sloan", "Smith", "Smoke", "Snake", "Snow", "Snowy", "Sol",
    "Solar", "Sonar", "Sonic", "Spark", "Spice", "Spike", "Spine", "Spire",
    "Splash", "Spock", "Spore", "Stag", "Star", "Steam", "Steel", "Stella",
    "Steve", "Sting", "Stone", "Storm", "Story", "Stout", "Sugar", "Sunny",
    "Surge", "Swap", "Swift", "Sword", "Syrup",
    # T
    "Taco", "Talon", "Tango", "Tank", "Tao", "Tara", "Tardy", "Ted",
    "Tempo", "Terra", "Terry", "Tess", "Tesla", "Tex", "Theo", "Thor",
    "Thorn", "Thyme", "Tide", "Tiger", "Tilly", "Tim", "Titan", "Toast",
    "Todd", "Token", "Tom", "Tonic", "Tony", "Topaz", "Torch", "Tower",
    "Trace", "Trade", "Trail", "Trait", "Trek", "Trend", "Trick", "Trix",
    "Tron", "Troop", "Troy", "True", "Trunk", "Trust", "Tudor", "Tulip",
    "Turbo", "Tweed", "Twist", "Tyler",
    # U
    "Uber", "Ultra", "Uma", "Umbra", "Unity", "Uno", "Upper", "Urban",
    "Ursa",
    # V
    "Val", "Valor", "Vault", "Venus", "Vera", "Verde", "Vex", "Vice",
    "Vigor", "Vince", "Vine", "Viola", "Viper", "Vista", "Vita", "Vivid",
    "Vixen", "Volta", "Vox",
    # W
    "Wade", "Waldo", "Walt", "Wanda", "Ward", "Warp", "Watch", "Wave",
    "Wayne", "Weave", "Wendy", "West", "Whale", "Wheat", "Whirl", "Whiz",
    "Wick", "Wilma", "Wily", "Wind", "Windy", "Wings", "Wink", "Wise",
    "Witch", "Wolf", "Woods", "Wren", "Wyatt",
    # X
    "Xander", "Xena", "Xero", "Xia", "Xylo",
    # Y
    "Yale", "Yara", "Yarn", "Yasuo", "Yogi", "York", "Yoshi", "Young",
    "Yuki", "Yuri", "Yves",
    # Z
    "Zack", "Zane", "Zany", "Zara", "Zeal", "Zelda", "Zen", "Zephyr",
    "Zero", "Ziggy", "Zinc", "Zinnia", "Zion", "Zippy", "Zoe", "Zola",
    "Zombie", "Zone", "Zoom", "Zora", "Zorro", "Zulu",
]
