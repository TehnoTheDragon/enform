# Form Format
## Overview
+ `<name>:<type> (, <name>:<type>)*` - fields
### Types
+ `i` - integer, may specify bitsize. `<name>:i<8, 16, 32, 64>(default: 8)`
+ `f` - number, may specify bitsize. `<name>:f<32, 64>(default: 32)`
+ `s` - string
+ `e` - enum, must define list of items `<name>:e[red,green,blue;`