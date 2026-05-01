(1..200).each{|n|puts n if (1...n).select{|i|n%i<1}.sum>n}
