# Map the official German data sheet to the unchanged evidence-field contract.
# Original columns are retained; aliases add no inferred clinical information.
library(readxl)
library(janitor)
p <- './src/1 bronze/staging area/Publications.xlsx'
d <- read_excel(p, sheet='Datenstamm', col_types='text')
required <- c('Handelsname','gal.Form/Dosierung','Packung','Wirkstoffe',
              'Swissmedic Code Packung','ATC-Code','Gammenbezeichnung','Listung (GGSL, SL, GGML)')
stopifnot(all(required %in% names(d)))
# The previous source scope was SL/GGSL. Keep this scope in the refresh.
print(table(d[['Listung (GGSL, SL, GGML)']],useNA='ifany'))
stopifnot(all(d[['Listung (GGSL, SL, GGML)']] %in% c('SL','GGSL','GGML')))
d$official_row <- as.character(seq_len(nrow(d))+1)
d <- d[d[['Listung (GGSL, SL, GGML)']] %in% c('SL','GGSL'),]
raw_names <- names(d)
d <- clean_names(d)
d$swissmedic_nr <- d$swissmedic_code_packung
# A current row can explicitly list several parallel-import package codes.
# Preserve the raw field and original row; expose each declared code separately.
parts <- lapply(d$swissmedic_nr,function(x) if (is.na(x) || x=='') NA_character_ else trimws(strsplit(x,',',fixed=TRUE)[[1]]))
d <- d[rep(seq_len(nrow(d)),lengths(parts)),]
d$swissmedic_nr <- unlist(parts)
valid <- !is.na(d$swissmedic_nr) & grepl('^[0-9]{1,8}$',d$swissmedic_nr)
stopifnot(all(valid | is.na(d$swissmedic_nr)))
d$zulassungsnummer <- ifelse(valid,as.character(floor(as.numeric(d$swissmedic_nr)/1000)),NA_character_)
d$atc <- d$atc_code
d$substanzen <- d$wirkstoffe
d$bezeichnung <- paste(d$handelsname, d$gal_form_dosierung, d$packung, sep=', ')
write.table(d,'./src/2 silver/staging area/sl.csv',row.names=FALSE,sep='|',fileEncoding='UTF-8')
print(c(records=nrow(d),columns=ncol(d)))
