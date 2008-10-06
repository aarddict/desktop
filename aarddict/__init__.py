from PyICU import Locale, Collator
ucollator =  Collator.createInstance(Locale('root'))
ucollator.setStrength(1)
