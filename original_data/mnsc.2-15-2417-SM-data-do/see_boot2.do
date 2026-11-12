capture program drop se_boot2
program define se_boot2, rclass

** Adapts Chetty et al (2011) procedure to return
** - actual number of finishers
** - predicted number of finishers
** - excess mass percentage
**
** TAKES AS INPUTS
** - `1' : bunchpoint or threshold
** - `2' : bin size (4 in Allen et al)
** - `3' : bunching window (8 in Allen et al)
 
preserve
bys round1_chiptime: egen round1_counter = count(_n)
replace round1_counter = round1_counter/1000

local bin = `2'
local bins = 4*`2'
local bins2 = `3' * `3' + 1


sort round1_chiptime
keep if round1_chiptime ~= round1_chiptime[_n-1]

gen round1_chiptime_sq = round1_chiptime*round1_chiptime
gen round1_chiptime_cb = round1_chiptime_sq*round1_chiptime
gen round1_chiptime_quar = round1_chiptime_cb*round1_chiptime
gen round1_chiptime_quin = round1_chiptime_quar*round1_chiptime


reg round1_counter round1_chiptime* if (round1_chiptime > (bunchpoint + 0) & round1_chiptime <= (bunchpoint + `3')) | (round1_chiptime < (bunchpoint - `bin') & round1_chiptime >= (bunchpoint - `3'))
predict yhat`1'


**we need to shift the polynomial fit up in order to make sure that the same mass is underneath the counterfactual and the real density function. 
egen realdensity`1' = sum(round1_counter) if round1_chiptime >= (bunchpoint - `3') & round1_chiptime <= (bunchpoint + `3') 
egen counterfactdensity`1' = sum(yhat`1') if round1_chiptime >= (bunchpoint - `3') & round1_chiptime <= (bunchpoint + `3')
gen addition`1' = (realdensity`1' - counterfactdensity`1')/`bins2'
replace yhat`1' = yhat`1' + addition`1'

*now we want to add up the number of excess finishers
sort round1_chiptime
gen actual_finishers`1' = round1_counter if round1_chiptime == bunchpoint
forvalues i = 1(1)`bins' {
qui replace actual_finishers`1' = actual_finishers`1' + round1_counter[_n-`i'] if round1_chiptime == bunchpoint
}
gen counterfact_finishers`1' = yhat`1' if round1_chiptime ==  bunchpoint
forvalues i = 1(1)`bins' {
qui replace counterfact_finishers`1' = counterfact_finishers`1' + yhat`1'[_n-`i'] if round1_chiptime == bunchpoint
}
gen excess_finishers`1' = actual_finishers`1' - counterfact_finishers`1' if round1_chiptime == bunchpoint
gen excess_perc`1' = excess_finishers`1'/counterfact_finishers`1' if round1_chiptime == bunchpoint

keep if round1_chiptime == bunchpoint


egen actual=mean(actual_finishers`1')
sum actual
return scalar actual = r(mean)*1000

egen counter=mean(counterfact_finishers`1')
sum counter
return scalar counter = r(mean)*1000

egen excess=mean(excess_finishers`1')
sum excess
return scalar excess = r(mean)*1000

return scalar outcome = excess_perc`1'

restore
end
