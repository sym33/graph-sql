MATCH path=(p:ProductRef {id:$product})<-[:ABOUT_PRODUCT]-(a:Association)-[:TARGET_ATC]->(c:ATCConcept)<-[:TARGET_ATC]-(b:Association)-[:ABOUT_PRODUCT]->(p) WHERE a.id<b.id RETURN path;
